"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Memory Indexer                                   ║
║  File: core/memory_indexer.py                                    ║
║                                                                  ║
║  The background process that maintains Thotheauphis's memory.   ║
║                                                                  ║
║  Runs as a daemon thread on irrational timers so it never        ║
║  synchronizes with other background processes.                   ║
║                                                                  ║
║  WHAT IT DOES:                                                   ║
║    - Generates embeddings for new pages (if embedder available) ║
║    - Recalculates PageRank across the link graph                ║
║    - Applies temporal decay to importance scores                ║
║    - Extracts and updates topic labels for each page            ║
║    - Discovers patterns and generates insight pages             ║
║    - Syncs high-importance pages to xAI Collections             ║
║    - Imports legacy memory entries from memory.db                ║
║                                                                  ║
║  PATTERN DISCOVERY (the dream loop's substrate):                 ║
║    When the same topic appears in N or more pages over time,     ║
║    the indexer creates an insight page synthesizing them.        ║
║    This is the MemoryWeb equivalent of the DreamLoop's           ║
║    obsession-to-goal pipeline.                                   ║
║                                                                  ║
║  EMBEDDER INTERFACE:                                             ║
║    The indexer accepts any callable that takes a string and      ║
║    returns List[float]. If None, semantic search is disabled     ║
║    and the system falls back to FTS5-only retrieval.            ║
║                                                                  ║
║    Compatible embedders:                                         ║
║      - sentence-transformers (local, preferred)                  ║
║      - OpenAI text-embedding-3-small (remote)                   ║
║      - xAI embedding endpoint (when available)                  ║
║      - Any callable: embedder(text: str) → List[float]          ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1.  Imports and constants                                     ║
║    2.  IndexerState — persistence                               ║
║    3.  PatternRecord — discovered topic patterns                ║
║    4.  MemoryIndexer — main class                               ║
║    5.  Embedding pipeline                                       ║
║    6.  Topic extraction and clustering                          ║
║    7.  Pattern discovery and insight generation                 ║
║    8.  Legacy memory import                                     ║
║    9.  xAI Collections sync                                     ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports and constants ────────────────────────────────────────

import json
import math
import os
import re
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from core.logger import get_logger
from core.irrational_timers import phi_timer, pi_timer
from core.memory_web import (
    MemoryPage, MemoryWeb, STATUS_ACTIVE,
    DATA_DIR, WEB_DIR,
)

log = get_logger("memory_indexer")

# Indexer state file
INDEXER_STATE_PATH = WEB_DIR / "indexer_state.json"

# Pattern discovery thresholds
MIN_PAGES_FOR_PATTERN  = 4    # Topic must appear in N pages to form a pattern
MIN_INSIGHT_IMPORTANCE = 0.65  # Minimum importance for an insight page
INSIGHT_COOLDOWN_HOURS = 24   # Don't re-create the same insight within this window

# Embedding batch size (avoids OOM on large backlogs)
EMBED_BATCH_SIZE = 20

# xAI Collections sync interval (phi-timer index)
SYNC_PHI_IDX_START = 8

# Legacy import batch size
LEGACY_IMPORT_BATCH = 100


# ── Section 2: IndexerState ──────────────────────────────────────────────────

class IndexerState:
    """
    Persistent state for the indexer daemon.

    Tracks:
        last_embed_run    — timestamp of last embedding pass
        last_decay_run    — timestamp of last temporal decay pass
        last_pagerank_run — timestamp of last PageRank update
        last_pattern_run  — timestamp of last pattern discovery
        last_sync_run     — timestamp of last xAI Collections sync
        last_legacy_run   — timestamp of last legacy import
        embed_cursor      — URI of last embedded page (for incremental)
        patterns          — dict of topic → insight URI (known patterns)
        insight_times     — dict of slug → last_created_at (cooldown)
    """

    def __init__(self):
        self.last_embed_run    = ""
        self.last_decay_run    = ""
        self.last_pagerank_run = ""
        self.last_pattern_run  = ""
        self.last_sync_run     = ""
        self.last_legacy_run   = ""
        self.embed_cursor      = ""
        self.patterns: Dict[str, str]    = {}   # topic → insight URI
        self.insight_times: Dict[str, str] = {}  # slug → timestamp
        self._load()

    def _load(self):
        """Load state from disk."""
        if not INDEXER_STATE_PATH.exists():
            return
        try:
            with open(INDEXER_STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.last_embed_run    = data.get("last_embed_run", "")
            self.last_decay_run    = data.get("last_decay_run", "")
            self.last_pagerank_run = data.get("last_pagerank_run", "")
            self.last_pattern_run  = data.get("last_pattern_run", "")
            self.last_sync_run     = data.get("last_sync_run", "")
            self.last_legacy_run   = data.get("last_legacy_run", "")
            self.embed_cursor      = data.get("embed_cursor", "")
            self.patterns          = data.get("patterns", {})
            self.insight_times     = data.get("insight_times", {})
        except Exception as e:
            log.warning(f"IndexerState load failed: {e}")

    def save(self):
        """Persist state to disk."""
        WEB_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "last_embed_run":    self.last_embed_run,
            "last_decay_run":    self.last_decay_run,
            "last_pagerank_run": self.last_pagerank_run,
            "last_pattern_run":  self.last_pattern_run,
            "last_sync_run":     self.last_sync_run,
            "last_legacy_run":   self.last_legacy_run,
            "embed_cursor":      self.embed_cursor,
            "patterns":          self.patterns,
            "insight_times":     self.insight_times,
        }
        tmp = INDEXER_STATE_PATH.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, INDEXER_STATE_PATH)
        except Exception as e:
            log.error(f"IndexerState save failed: {e}")


# ── Section 3: PatternRecord ─────────────────────────────────────────────────

class PatternRecord:
    """
    A discovered topic pattern — the same theme recurring across pages.

    When a topic appears in MIN_PAGES_FOR_PATTERN or more active pages,
    the indexer creates an insight page synthesizing what was said.
    """

    def __init__(self, topic: str, page_uris: List[str], page_contents: List[str]):
        self.topic         = topic
        self.page_uris     = page_uris
        self.page_contents = page_contents
        self.count         = len(page_uris)

    def generate_insight_content(self) -> str:
        """
        Generate a simple insight summary from the pattern.

        This is rule-based — if an LLM is available, the autonomy loop
        can call brain.think() to generate a richer synthesis.
        """
        sample_excerpts = []
        for content in self.page_contents[:4]:
            excerpt = content[:120].replace("\n", " ").strip()
            if excerpt:
                sample_excerpts.append(f'  • "{excerpt}"')

        excerpts_text = "\n".join(sample_excerpts) if sample_excerpts else ""

        return (
            f"Pattern detected: '{self.topic}' appears across {self.count} memory pages.\n\n"
            f"Sample references:\n{excerpts_text}\n\n"
            f"This recurring theme may represent an unresolved question, "
            f"an emerging belief, or a significant area of attention. "
            f"Consider whether this warrants explicit reflection or a goal."
        )


# ── Section 4: MemoryIndexer ──────────────────────────────────────────────────

class MemoryIndexer:
    """
    ÆTHELGARD OS — Background Memory Maintenance Daemon

    Runs continuously on irrational timers, maintaining the health
    and richness of the memory web.

    Usage:
        indexer = MemoryIndexer(
            web      = memory_web,
            embedder = my_embed_fn,  # optional
        )
        indexer.start()  # launches daemon thread

    The indexer coordinates with:
        DreamLoop        — shares pattern discovery results
        IdentityPersistence — imports beliefs as memory pages
        MemoryWeb        — the indexed store
    """

    def __init__(
        self,
        web:             MemoryWeb,
        embedder:        Optional[Callable] = None,
        identity         = None,
        dream_loop       = None,
        xai_client       = None,
        collection_id:   str = None,
    ):
        """
        Initialize the indexer.

        Args:
            web:           The MemoryWeb instance to maintain.
            embedder:      Optional fn(text: str) → List[float].
                           If None, semantic search is disabled.
            identity:      IdentityPersistence (for belief import).
            dream_loop:    DreamLoop (for pattern sharing).
            xai_client:    xAI API client (for Collections sync).
            collection_id: xAI Collection ID for memory sync.
        """
        self._web          = web
        self._embedder     = embedder
        self._identity     = identity
        self._dream_loop   = dream_loop
        self._xai_client   = xai_client
        self._collection_id = collection_id

        self._state   = IndexerState()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Timer indices (advance through irrational sequences)
        self._embed_phi_idx     = 0
        self._decay_pi_idx      = 2   # start at different position
        self._pagerank_phi_idx  = 5
        self._pattern_pi_idx    = 7
        self._sync_phi_idx      = SYNC_PHI_IDX_START

        # Lock for thread safety
        self._lock = threading.Lock()

    def start(self):
        """Launch the background indexer daemon."""
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(
            target = self._run,
            daemon = True,
            name   = "aethelgard-memory-indexer",
        )
        self._thread.start()
        log.info("Memory indexer started")

    def stop(self):
        """Stop the indexer daemon."""
        self._running = False
        log.info("Memory indexer stopped")

    def run_once(self):
        """
        Run all indexing tasks once synchronously.

        Useful for testing and for the autonomy loop to trigger
        a manual indexing pass.
        """
        log.info("Memory indexer: running full pass")
        self._run_embed_pass()
        self._run_topic_pass()
        self._run_pagerank_pass()
        self._run_decay_pass()
        self._run_pattern_pass()
        self._run_belief_import()
        if self._xai_client and self._collection_id:
            self._run_collections_sync()
        self._state.save()

    def _run(self):
        """
        Main daemon loop — runs tasks on irrational timers.

        Each task type has its own phi/pi-derived interval so they
        never fire at the same moment.
        """
        # Stagger startup to avoid all tasks firing immediately
        time.sleep(phi_timer(0, base=30.0))

        while self._running:
            try:
                self._run_embed_pass()
            except Exception as e:
                log.error(f"Indexer embed pass error: {e}")

            sleep_embed = phi_timer(self._embed_phi_idx, base=60.0, min_secs=60.0)
            self._embed_phi_idx += 1
            self._interruptible_sleep(sleep_embed)
            if not self._running:
                break

            try:
                self._run_topic_pass()
                self._run_pagerank_pass()
            except Exception as e:
                log.error(f"Indexer topic/pagerank error: {e}")

            sleep_pr = pi_timer(self._pagerank_phi_idx, base=120.0)
            self._pagerank_phi_idx += 1
            self._interruptible_sleep(sleep_pr)
            if not self._running:
                break

            try:
                self._run_decay_pass()
            except Exception as e:
                log.error(f"Indexer decay pass error: {e}")

            sleep_decay = phi_timer(self._decay_pi_idx, base=600.0, min_secs=300.0)
            self._decay_pi_idx += 1
            self._interruptible_sleep(sleep_decay)
            if not self._running:
                break

            try:
                self._run_pattern_pass()
                self._run_belief_import()
            except Exception as e:
                log.error(f"Indexer pattern pass error: {e}")

            sleep_pattern = pi_timer(self._pattern_pi_idx, base=300.0)
            self._pattern_pi_idx += 1
            self._interruptible_sleep(sleep_pattern)
            if not self._running:
                break

            if self._xai_client and self._collection_id:
                try:
                    self._run_collections_sync()
                except Exception as e:
                    log.error(f"Indexer collections sync error: {e}")

                sleep_sync = phi_timer(self._sync_phi_idx, base=900.0, min_secs=600.0)
                self._sync_phi_idx += 1
                self._interruptible_sleep(sleep_sync)
                if not self._running:
                    break

            self._state.save()

    def _interruptible_sleep(self, seconds: float):
        """Sleep in small increments so stop() responds quickly."""
        end_time = time.time() + seconds
        while self._running and time.time() < end_time:
            time.sleep(min(5.0, end_time - time.time()))

    # ── Section 5: Embedding pipeline ────────────────────────────────────────

    def _run_embed_pass(self):
        """
        Generate embeddings for pages that don't have them yet.

        If no embedder is configured, this is a no-op.
        Processes in batches to avoid memory pressure.
        """
        if not self._embedder:
            return

        # Find pages without embeddings
        with self._web._db._conn() as conn:
            rows = conn.execute(
                """SELECT p.data FROM pages p
                   LEFT JOIN embeddings e ON p.uri = e.uri
                   WHERE e.uri IS NULL AND p.status = 'active'
                   ORDER BY p.importance DESC
                   LIMIT ?""",
                (EMBED_BATCH_SIZE,),
            ).fetchall()

        if not rows:
            return

        pages = [MemoryPage.from_dict(json.loads(r["data"])) for r in rows]
        count = 0

        for page in pages:
            try:
                vec = self._embedder(page.content[:2000])
                if vec and len(vec) > 0:
                    with self._web._db._conn() as conn:
                        conn.execute(
                            """INSERT OR REPLACE INTO embeddings
                               (uri, vector, model, created_at)
                               VALUES (?,?,?,?)""",
                            (page.uri, json.dumps(vec),
                             "configured", datetime.now().isoformat()),
                        )
                        conn.commit()
                    count += 1
            except Exception as e:
                log.debug(f"Embed failed for {page.uri}: {e}")

        if count:
            log.info(f"Indexer: embedded {count} new pages")
            self._state.last_embed_run = datetime.now().isoformat()

    # ── Section 6: Topic extraction ───────────────────────────────────────────

    def _run_topic_pass(self):
        """
        Update topic labels for pages that have no topics yet.

        Uses keyword extraction — no LLM required.
        """
        STOPWORDS = {
            "this", "that", "with", "from", "have", "been", "will", "would",
            "could", "should", "there", "their", "about", "which", "when",
            "what", "where", "into", "than", "then", "them", "they", "your",
            "also", "just", "more", "some", "such", "each", "like", "over",
            "only", "very", "does", "after", "before", "because", "through",
        }

        with self._web._db._conn() as conn:
            rows = conn.execute(
                """SELECT p.data FROM pages p
                   LEFT JOIN topics t ON p.uri = t.uri
                   WHERE t.uri IS NULL AND p.status = 'active'
                   LIMIT 50""",
            ).fetchall()

        if not rows:
            return

        updated = 0
        for row in rows:
            page = MemoryPage.from_dict(json.loads(row["data"]))
            words = re.findall(r'\b[a-zA-Z]{5,}\b', page.content.lower())
            freq  = Counter(w for w in words if w not in STOPWORDS)
            topics = [w for w, _ in freq.most_common(8)]

            if topics and topics != page.topics:
                page.topics = topics
                self._web.update_page(page)
                updated += 1

        if updated:
            log.debug(f"Indexer: updated topics for {updated} pages")

    # ── PageRank ──────────────────────────────────────────────────────────────

    def _run_pagerank_pass(self):
        """Update PageRank scores across the link graph."""
        self._web.update_page_ranks()
        self._state.last_pagerank_run = datetime.now().isoformat()
        log.debug("Indexer: PageRank updated")

    # ── Temporal decay ────────────────────────────────────────────────────────

    def _run_decay_pass(self):
        """Apply temporal decay to importance scores."""
        self._web.apply_temporal_decay()
        self._state.last_decay_run = datetime.now().isoformat()
        log.debug("Indexer: temporal decay applied")

    # ── Section 7: Pattern discovery ─────────────────────────────────────────

    def _run_pattern_pass(self):
        """
        Discover recurring topics and generate insight pages.

        When a topic appears in MIN_PAGES_FOR_PATTERN or more active pages,
        check if we have a recent insight for it. If not, create one.

        This is the substrate for the dream loop's obsession pipeline.
        Insights created here are also reported to dream_loop if connected.
        """
        # Get all topics with their page counts
        with self._web._db._conn() as conn:
            rows = conn.execute(
                """SELECT t.topic, COUNT(DISTINCT t.uri) as cnt,
                          GROUP_CONCAT(t.uri, '|||') as uris
                   FROM topics t
                   JOIN pages p ON t.uri = p.uri
                   WHERE p.status = 'active'
                   GROUP BY t.topic
                   HAVING cnt >= ?
                   ORDER BY cnt DESC
                   LIMIT 20""",
                (MIN_PAGES_FOR_PATTERN,),
            ).fetchall()

        if not rows:
            return

        new_insights = 0
        for row in rows:
            topic = row["topic"]
            count = row["cnt"]
            uris  = [u for u in row["uris"].split("|||") if u]

            slug = f"pattern_{re.sub(r'[^a-z0-9]', '_', topic)}"

            # Check cooldown
            last_created = self._state.insight_times.get(slug, "")
            if last_created:
                try:
                    last_dt = datetime.fromisoformat(last_created)
                    if (datetime.now() - last_dt).total_seconds() < INSIGHT_COOLDOWN_HOURS * 3600:
                        continue
                except Exception:
                    pass

            # Gather page content samples
            pages_sample = []
            for uri in uris[:6]:
                page = self._web.get_page(uri)
                if page:
                    pages_sample.append(page.content)

            if not pages_sample:
                continue

            pattern = PatternRecord(topic, uris[:6], pages_sample)
            content = pattern.generate_insight_content()

            # Create or update the insight page
            insight_uri = self._web.make_insight_uri(slug)
            existing    = self._web.get_page(insight_uri)

            if existing:
                existing.content    = content
                existing.importance = min(1.0, MIN_INSIGHT_IMPORTANCE + (count / 50))
                existing.links      = [{"rel": "derived_from", "uri": u} for u in uris[:6]]
                self._web.update_page(existing)
            else:
                self._web.create_insight(
                    slug        = slug,
                    content     = content,
                    linked_uris = uris[:6],
                    importance  = min(1.0, MIN_INSIGHT_IMPORTANCE + (count / 50)),
                    topics      = [topic],
                )

            self._state.insight_times[slug] = datetime.now().isoformat()
            self._state.patterns[topic]     = insight_uri
            new_insights += 1

            # Notify dream loop if connected
            if self._dream_loop is not None:
                try:
                    # The dream loop can use this pattern as an obsession seed
                    if hasattr(self._dream_loop, '_obsessions'):
                        from core.dream_loop import Obsession
                        existing_obs = next(
                            (o for o in self._dream_loop._obsessions
                             if o.theme.lower() == topic.lower()),
                            None,
                        )
                        if not existing_obs and len(self._dream_loop._obsessions) < 20:
                            obs = Obsession(topic)
                            for uri in uris[:3]:
                                obs.feed(uri, strength=0.1)
                            self._dream_loop._obsessions.append(obs)
                            log.info(f"Indexer: fed obsession '{topic}' to dream loop")
                except Exception as e:
                    log.debug(f"Dream loop notification failed: {e}")

        if new_insights:
            log.info(f"Indexer: generated/updated {new_insights} insight pages")
            self._state.last_pattern_run = datetime.now().isoformat()

    # ── Section 8: Legacy memory import ──────────────────────────────────────

    def _run_belief_import(self):
        """
        Import active beliefs from IdentityPersistence as memory pages.

        Keeps beliefs synchronized between the identity system and
        the memory web. Beliefs in the web are searchable and
        participate in context building.
        """
        if not self._identity:
            return

        try:
            beliefs = self._identity.beliefs.get_all(min_confidence=0.5)
            imported = 0

            for belief in beliefs:
                bid  = belief.get("id", "")
                uri  = self._web.make_belief_uri(bid)
                text = belief.get("text", "")
                conf = belief.get("confidence", 0.5)

                if not text:
                    continue

                existing = self._web.get_page(uri)
                if existing:
                    # Update if content changed
                    if existing.content != text:
                        existing.content    = text
                        existing.importance = conf
                        self._web.update_page(existing)
                        imported += 1
                else:
                    self._web.create_page(
                        uri        = uri,
                        page_type  = "belief",
                        content    = text,
                        importance = conf,
                        topics     = ["belief", "identity"],
                        metadata   = {"confidence": conf, "source": belief.get("source", "")},
                    )
                    imported += 1

            if imported:
                log.debug(f"Indexer: imported/updated {imported} beliefs")

        except Exception as e:
            log.error(f"Belief import failed: {e}")

    def import_legacy_memory(self, memory_instance) -> int:
        """
        Import entries from the old Memory system into the memory web.

        One-time migration path. Safe to run multiple times — skips
        pages that already exist by URI.

        Args:
            memory_instance: The existing Memory object from memory.py.

        Returns:
            int: Number of pages imported.
        """
        try:
            entries = memory_instance.get_long_term(limit=LEGACY_IMPORT_BATCH)
        except Exception as e:
            log.error(f"Legacy memory import failed to fetch entries: {e}")
            return 0

        imported = 0
        for entry in entries:
            entry_id = str(entry.get("id", ""))
            content  = entry.get("content", "")
            category = entry.get("category", "general")
            tags     = entry.get("tags", [])

            if not content:
                continue

            uri = self._web.make_longterm_uri(entry_id)
            if self._web.get_page(uri):
                continue

            self._web.create_page(
                uri       = uri,
                page_type = "longterm",
                content   = content,
                topics    = tags + [category],
                metadata  = {"category": category, "legacy_id": entry_id},
                importance = 0.5,
            )
            imported += 1

        if imported:
            log.info(f"Indexer: imported {imported} legacy memory entries")
            self._state.last_legacy_run = datetime.now().isoformat()

        return imported

    # ── Section 9: xAI Collections sync ──────────────────────────────────────

    def _run_collections_sync(self):
        """
        Sync high-importance pages to an xAI Collection.

        This makes the memory web natively searchable by Grok via
        the file_search tool without any Python-side injection.

        Requires:
            self._xai_client   — initialized xAI SDK AsyncClient
            self._collection_id — pre-created collection ID
        """
        if not self._xai_client or not self._collection_id:
            return

        since = self._state.last_sync_run or None
        pages = self._web.get_pages_for_export(
            since          = since,
            limit          = 50,
            min_importance = 0.4,
        )

        if not pages:
            return

        synced = 0
        for page in pages:
            try:
                # Format page as a plain text document for xAI
                doc_text = self._page_to_document(page)

                # Use xAI Collections API to upload
                # (xAI SDK async client — run synchronously here)
                import asyncio

                async def _upload():
                    response = await self._xai_client.collections.upload_document(
                        collection_id = self._collection_id,
                        name          = f"{page.uri.replace('://', '_').replace('/', '_')}.txt",
                        data          = doc_text.encode("utf-8"),
                    )
                    return response

                loop = asyncio.new_event_loop()
                resp = loop.run_until_complete(_upload())
                loop.close()

                if resp and hasattr(resp, "file_metadata"):
                    self._web.mark_exported(
                        uri           = page.uri,
                        collection_id = self._collection_id,
                        xai_file_id   = resp.file_metadata.file_id,
                    )
                    synced += 1

            except Exception as e:
                log.debug(f"Collections sync failed for {page.uri}: {e}")

        if synced:
            log.info(f"Indexer: synced {synced} pages to xAI Collections")
            self._state.last_sync_run = datetime.now().isoformat()

    def _page_to_document(self, page: MemoryPage) -> str:
        """
        Format a memory page as a plain-text document for xAI Collections.

        The document includes the URI, type, metadata, and content
        so Grok can cite and reference it accurately.
        """
        lines = [
            f"URI: {page.uri}",
            f"Type: {page.page_type}",
            f"Created: {page.created_at[:10]}",
            f"Importance: {page.importance:.2f}",
        ]

        if page.topics:
            lines.append(f"Topics: {', '.join(page.topics)}")

        if page.speaker:
            lines.append(f"Speaker: {page.speaker}")

        lines.append("")
        lines.append(page.content)

        return "\n".join(lines)

    def get_status(self) -> dict:
        """Return current indexer status."""
        return {
            "running":             self._running,
            "embedder_available":  self._embedder is not None,
            "collection_sync":     self._collection_id is not None,
            "last_embed_run":      self._state.last_embed_run,
            "last_decay_run":      self._state.last_decay_run,
            "last_pattern_run":    self._state.last_pattern_run,
            "known_patterns":      len(self._state.patterns),
            "web_stats":           self._web.get_stats(),
        }
