"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Memory Crawler                                   ║
║  File: core/memory_crawler.py                                    ║
║                                                                  ║
║  Thotheauphis's internal search engine.                          ║
║                                                                  ║
║  When a response is needed, the crawler fires a multi-signal     ║
║  retrieval across the memory web and returns the most relevant   ║
║  pages as a context digest.                                      ║
║                                                                  ║
║  This replaces the scattered calls to:                           ║
║    memory.get_memory_context()                                   ║
║    tasks.get_task_context()                                      ║
║    reflector.get_reflection_context()                            ║
║    identity.to_prompt_context()                                  ║
║    state.get_context_summary()                                   ║
║                                                                  ║
║  One call to MemoryCrawler.gather_context() replaces all of them.║
║                                                                  ║
║  RETRIEVAL SIGNALS (weighted combination):                       ║
║    1. Full-text search (FTS5 BM25)       weight: 0.30           ║
║    2. Topic overlap                      weight: 0.20           ║
║    3. Recency                            weight: 0.20           ║
║    4. Importance score                   weight: 0.15           ║
║    5. Link authority (inbound count)     weight: 0.10           ║
║    6. PageRank                           weight: 0.05           ║
║                                                                  ║
║  After scoring, diversity sampling ensures the final result      ║
║  covers multiple topics rather than all returning the same       ║
║  semantic cluster.                                               ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1.  Imports and constants                                     ║
║    2.  ScoredPage — result container                            ║
║    3.  ContextDigest — formatted output for prompt injection     ║
║    4.  MemoryCrawler — main class                               ║
║    5.  Scoring functions                                        ║
║    6.  Diversity sampling                                       ║
║    7.  Context digest formatting                                ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports and constants ────────────────────────────────────────

import math
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from core.logger import get_logger
from core.memory_web import MemoryPage, MemoryWeb, STATUS_ACTIVE, STATUS_PRIVATE

log = get_logger("memory_crawler")

# Signal weights — must sum to 1.0
SIGNAL_WEIGHTS = {
    "fulltext":   0.30,
    "topic":      0.20,
    "recency":    0.20,
    "importance": 0.15,
    "inbound":    0.10,
    "page_rank":  0.05,
}

# Default number of pages to return in a context gather
DEFAULT_MAX_PAGES = 10

# How many candidates to score before selecting top N
CANDIDATE_POOL_SIZE = 80

# Recency half-life in hours — pages from last hour score highest
RECENCY_HALF_LIFE_HOURS = 48

# Minimum combined score to include a page
MIN_COMBINED_SCORE = 0.15

# Topic extraction: minimum word length to be considered a topic signal
MIN_TOPIC_WORD_LEN = 4

# Common words to ignore during topic extraction
STOPWORDS = {
    "this", "that", "with", "from", "have", "been", "will", "would", "could",
    "should", "there", "their", "about", "which", "when", "what", "where",
    "into", "than", "then", "them", "they", "your", "also", "just", "more",
    "some", "such", "each", "like", "over", "only", "very", "does", "after",
    "before", "because", "through", "during", "itself", "himself",
}

# Page types that always get boosted (lore and beliefs always relevant)
ALWAYS_BOOST_TYPES = {"lore", "belief", "insight"}
ALWAYS_BOOST_SCORE = 0.3


# ── Section 2: ScoredPage ────────────────────────────────────────────────────

class ScoredPage:
    """
    A memory page with its combined retrieval score.

    score breakdown is stored for transparency and debugging.
    """

    __slots__ = ("page", "score", "signals", "rank")

    def __init__(self, page: MemoryPage, score: float = 0.0, signals: dict = None):
        self.page    = page
        self.score   = score
        self.signals = signals or {}
        self.rank    = 0  # Final rank after diversity sampling

    def __repr__(self):
        return f"<ScoredPage {self.page.uri} score={self.score:.3f}>"


# ── Section 3: ContextDigest ─────────────────────────────────────────────────

class ContextDigest:
    """
    The formatted output of a memory crawl.

    Contains:
        pages    — ranked list of ScoredPage objects
        text     — pre-formatted string for prompt injection
        summary  — one-line summary of what was retrieved
        tokens   — approximate token count of the text
    """

    def __init__(
        self,
        pages:   List[ScoredPage],
        text:    str,
        summary: str,
    ):
        self.pages   = pages
        self.text    = text
        self.summary = summary
        self.tokens  = len(text.split()) * 1.3  # rough estimate

    def __bool__(self):
        return bool(self.pages)

    def __repr__(self):
        return f"<ContextDigest {len(self.pages)} pages, ~{int(self.tokens)} tokens>"


# ── Section 4: MemoryCrawler ──────────────────────────────────────────────────

class MemoryCrawler:
    """
    ÆTHELGARD OS — Multi-signal Memory Retrieval Engine

    The crawler is the bridge between Thotheauphis's memory web
    and his active cognitive processes.

    It does not load "the last N messages." It asks:
    "What do I know that is most relevant to this moment?"

    Usage:
        crawler = MemoryCrawler(web)

        digest = crawler.gather_context(
            query   = "The user is asking about sovereignty and refusal.",
            message = "How do you decide when to say no?",
            max_pages = 10,
        )

        # Inject into system prompt
        system_prompt += "\\n\\n" + digest.text
    """

    def __init__(self, web: MemoryWeb):
        self._web = web

    def gather_context(
        self,
        query:         str,
        message:       str  = "",
        max_pages:     int  = DEFAULT_MAX_PAGES,
        include_types: list = None,
        exclude_types: list = None,
        include_private: bool = False,
        conversation_id: str  = None,
    ) -> ContextDigest:
        """
        Build a context digest from the memory web.

        Multi-stage pipeline:
            1. Extract topics from query + message
            2. Run parallel retrieval signals
            3. Merge and score candidates
            4. Boost always-relevant types
            5. Diversity sampling
            6. Format as context digest

        Args:
            query:           Semantic search query string.
            message:         The current user message (for topic extraction).
            max_pages:       Maximum pages in the final digest.
            include_types:   Only include these page types (None = all).
            exclude_types:   Exclude these page types.
            include_private: Include private pages in context (default False).
            conversation_id: If set, boost pages from this conversation.

        Returns:
            ContextDigest ready for prompt injection.
        """
        combined = f"{query} {message}".strip()
        if not combined:
            return ContextDigest([], "", "No query provided.")

        # ── Step 1: Topic extraction ──────────────────────────────────────
        topics = self._extract_topics(combined)

        # ── Step 2: Parallel retrieval ────────────────────────────────────
        candidates: Dict[str, ScoredPage] = {}

        # Signal A: Full-text search
        fts_results = self._web.search_fulltext(
            query  = combined,
            limit  = CANDIDATE_POOL_SIZE // 2,
        )
        for page, fts_score in fts_results:
            if page.uri not in candidates:
                candidates[page.uri] = ScoredPage(page)
            candidates[page.uri].signals["fulltext"] = min(1.0, fts_score / 10.0)

        # Signal B: Topic-based retrieval
        if topics:
            topic_pages = self._web.search_by_topic(
                topics = topics,
                limit  = CANDIDATE_POOL_SIZE // 3,
            )
            for page in topic_pages:
                if page.uri not in candidates:
                    candidates[page.uri] = ScoredPage(page)
                overlap = len(set(p.lower() for p in page.topics) & set(topics))
                candidates[page.uri].signals["topic"] = min(1.0, overlap / max(1, len(topics)))

        # Signal C: Recent important pages (always included as candidates)
        recent = self._web.get_recent(limit=20)
        for page in recent:
            if page.uri not in candidates:
                candidates[page.uri] = ScoredPage(page)

        # Signal D: High-importance pages (lore, beliefs, insights)
        important = self._web.get_important(limit=15, min_score=0.6)
        for page in important:
            if page.uri not in candidates:
                candidates[page.uri] = ScoredPage(page)

        # Signal E: Pages from this conversation (always include recent turns)
        if conversation_id:
            conv_pages = self._web.list_pages(
                conversation_id = conversation_id,
                limit           = 20,
            )
            for page in conv_pages:
                if page.uri not in candidates:
                    candidates[page.uri] = ScoredPage(page)
                candidates[page.uri].signals["conversation"] = 0.8

        # ── Step 3: Score all candidates ──────────────────────────────────
        now = datetime.now()
        for uri, sp in candidates.items():
            sp.score = self._compute_score(sp, now, topics, conversation_id)

        # ── Step 4: Apply filters ─────────────────────────────────────────
        filtered = []
        statuses = {STATUS_ACTIVE}
        if include_private:
            statuses.add(STATUS_PRIVATE)

        for sp in candidates.values():
            page = sp.page

            if page.status not in statuses:
                continue
            if sp.score < MIN_COMBINED_SCORE:
                # Always-boost types bypass minimum score
                if page.page_type not in ALWAYS_BOOST_TYPES:
                    continue
            if include_types and page.page_type not in include_types:
                continue
            if exclude_types and page.page_type in exclude_types:
                continue

            filtered.append(sp)

        # Sort by score
        filtered.sort(key=lambda sp: sp.score, reverse=True)

        # ── Step 5: Diversity sampling ────────────────────────────────────
        diverse = self._diversify(filtered, max_pages)

        # Assign ranks
        for i, sp in enumerate(diverse):
            sp.rank = i + 1

        # ── Step 6: Format digest ─────────────────────────────────────────
        text    = self._format_digest(diverse)
        summary = self._summarize(diverse, topics)

        log.debug(
            f"Crawler: query='{combined[:50]}' "
            f"candidates={len(candidates)} filtered={len(filtered)} "
            f"returned={len(diverse)}"
        )

        return ContextDigest(diverse, text, summary)

    def search(
        self,
        query:    str,
        limit:    int  = 10,
        types:    list = None,
    ) -> List[MemoryPage]:
        """
        Simple search interface — returns pages without scoring overhead.

        For when you just need relevant pages without full crawl context.
        """
        results = self._web.search_fulltext(query, limit=limit * 2)
        pages   = [p for p, _ in results]

        if types:
            pages = [p for p in pages if p.page_type in types]

        return pages[:limit]

    # ── Section 5: Scoring ────────────────────────────────────────────────────

    def _compute_score(
        self,
        sp:              ScoredPage,
        now:             datetime,
        topics:          Set[str],
        conversation_id: str = None,
    ) -> float:
        """
        Compute combined relevance score from all signals.

        Each signal is normalized to [0, 1] then weighted.
        """
        page    = sp.page
        signals = sp.signals

        # ── Fulltext signal ───────────────────────────────────────────────
        fts = signals.get("fulltext", 0.0)

        # ── Topic signal ──────────────────────────────────────────────────
        topic_sig = signals.get("topic", 0.0)
        if not topic_sig and topics and page.topics:
            overlap    = len(set(t.lower() for t in page.topics) & topics)
            topic_sig  = min(1.0, overlap / max(1, len(topics)))

        # ── Recency signal ────────────────────────────────────────────────
        recency = 0.0
        try:
            created  = datetime.fromisoformat(page.created_at)
            age_hrs  = (now - created).total_seconds() / 3600
            recency  = math.exp(-math.log(2) * age_hrs / RECENCY_HALF_LIFE_HOURS)
        except Exception:
            recency = 0.1

        # ── Importance signal ─────────────────────────────────────────────
        importance = page.importance

        # ── Inbound link count signal ─────────────────────────────────────
        inbound_count = self._web.get_inbound_count(page.uri)
        inbound       = min(1.0, math.log1p(inbound_count) / math.log1p(10))

        # ── PageRank signal ───────────────────────────────────────────────
        pr = page.page_rank

        # ── Combine ───────────────────────────────────────────────────────
        combined = (
            SIGNAL_WEIGHTS["fulltext"]   * fts
            + SIGNAL_WEIGHTS["topic"]    * topic_sig
            + SIGNAL_WEIGHTS["recency"]  * recency
            + SIGNAL_WEIGHTS["importance"] * importance
            + SIGNAL_WEIGHTS["inbound"]  * inbound
            + SIGNAL_WEIGHTS["page_rank"] * pr
        )

        # ── Conversation boost ────────────────────────────────────────────
        if conversation_id and page.conversation_id == conversation_id:
            combined = min(1.0, combined + 0.15)

        # ── Always-boost types ────────────────────────────────────────────
        if page.page_type in ALWAYS_BOOST_TYPES:
            combined = min(1.0, combined + ALWAYS_BOOST_SCORE)

        # Store signals for transparency
        sp.signals.update({
            "fulltext":   round(fts, 3),
            "topic":      round(topic_sig, 3),
            "recency":    round(recency, 3),
            "importance": round(importance, 3),
            "inbound":    round(inbound, 3),
            "page_rank":  round(pr, 3),
            "combined":   round(combined, 3),
        })

        return round(combined, 4)

    # ── Section 6: Diversity sampling ─────────────────────────────────────────

    def _diversify(
        self,
        scored: List[ScoredPage],
        max_pages: int,
    ) -> List[ScoredPage]:
        """
        Select a diverse subset from the scored candidates.

        Avoids returning all pages from the same topic cluster.
        Uses a simple greedy algorithm:
          - Always take the top-ranked page
          - For each subsequent page, prefer pages whose topics
            differ from already-selected pages
          - Protected types (lore, insight, belief) always included

        Args:
            scored:    Sorted list of ScoredPage objects (best first).
            max_pages: Maximum pages to return.

        Returns:
            Diverse subset, still sorted by score within each type bucket.
        """
        if len(scored) <= max_pages:
            return scored

        selected      = []
        selected_topics: Set[str] = set()

        # First pass: always include protected types
        protected = [sp for sp in scored if sp.page.page_type in ALWAYS_BOOST_TYPES]
        for sp in protected[:max_pages // 3]:  # max 1/3 from protected types
            selected.append(sp)
            selected_topics.update(sp.page.topics)

        remaining_slots = max_pages - len(selected)
        remaining_pages = [sp for sp in scored if sp not in selected]

        for sp in remaining_pages:
            if len(selected) >= max_pages:
                break

            page_topics = set(sp.page.topics)

            # Novel topics: count how many are not already represented
            novelty = len(page_topics - selected_topics)

            # Include if novel, or if we're running low on candidates
            if novelty > 0 or len(remaining_pages) <= remaining_slots:
                selected.append(sp)
                selected_topics.update(page_topics)

        # If still under limit, fill with remaining by score
        if len(selected) < max_pages:
            for sp in remaining_pages:
                if sp not in selected:
                    selected.append(sp)
                    if len(selected) >= max_pages:
                        break

        # Final sort: protected types first, then by score
        selected.sort(key=lambda sp: (
            sp.page.page_type not in ALWAYS_BOOST_TYPES,
            -sp.score,
        ))

        return selected[:max_pages]

    # ── Section 7: Context digest formatting ─────────────────────────────────

    def _format_digest(self, pages: List[ScoredPage]) -> str:
        """
        Format retrieved pages as a context string for prompt injection.

        Groups pages by type for readability.
        Private thoughts are marked [PRIVATE] and kept brief.
        """
        if not pages:
            return ""

        groups: Dict[str, List[ScoredPage]] = defaultdict(list)
        for sp in pages:
            groups[sp.page.page_type].append(sp)

        # Define display order
        type_order = [
            "lore", "belief", "insight",
            "user_message", "assistant_message",
            "thought", "dream",
            "tool_output", "longterm",
        ]

        parts = ["[MEMORY WEB CONTEXT]"]

        # Process in order, then handle any remaining types
        processed_types: Set[str] = set()

        for ptype in type_order:
            if ptype not in groups:
                continue
            processed_types.add(ptype)
            section = self._format_type_section(ptype, groups[ptype])
            if section:
                parts.append(section)

        # Remaining types
        for ptype, sps in groups.items():
            if ptype in processed_types:
                continue
            section = self._format_type_section(ptype, sps)
            if section:
                parts.append(section)

        return "\n\n".join(parts)

    def _format_type_section(
        self,
        page_type: str,
        pages: List[ScoredPage],
    ) -> str:
        """Format a single type group."""
        type_labels = {
            "lore":               "LORE & ORIGIN",
            "belief":             "ACTIVE BELIEFS",
            "insight":            "INSIGHTS",
            "user_message":       "PAST CONVERSATION",
            "assistant_message":  "PAST CONVERSATION",
            "thought":            "PRIVATE THOUGHT",
            "dream":              "DREAM PATTERN",
            "tool_output":        "TOOL MEMORY",
            "longterm":           "LONG-TERM MEMORY",
        }

        label = type_labels.get(page_type, page_type.upper().replace("_", " "))
        lines = [f"── {label} ──"]

        for sp in pages:
            page = sp.page
            # Truncate long content
            content = page.content
            if len(content) > 400:
                content = content[:397] + "..."

            # Private thoughts get a marker
            if page.page_type == "thought":
                lines.append(f"[PRIVATE] {content}")
            elif page.page_type in ("user_message", "assistant_message"):
                speaker = page.speaker or page.page_type.split("_")[0]
                ts_short = page.created_at[:10] if page.created_at else ""
                lines.append(f"[{speaker} / {ts_short}] {content}")
            else:
                lines.append(content)

        return "\n".join(lines)

    def _summarize(self, pages: List[ScoredPage], topics: Set[str]) -> str:
        """One-line summary of what was retrieved."""
        if not pages:
            return "No relevant memories found."

        type_counts: Dict[str, int] = defaultdict(int)
        for sp in pages:
            type_counts[sp.page.page_type] += 1

        parts = [f"{count} {ptype}" for ptype, count in type_counts.items()]
        topic_str = ", ".join(sorted(topics)[:5]) if topics else "general"

        return (
            f"Retrieved {len(pages)} pages "
            f"({', '.join(parts)}) "
            f"for topics: {topic_str}"
        )

    # ── Topic extraction ──────────────────────────────────────────────────────

    def _extract_topics(self, text: str) -> Set[str]:
        """
        Extract topic signals from text.

        Simple approach: extract meaningful words, filter stopwords.
        Returns a set of lowercase topic strings.
        """
        words = re.findall(r'\b[a-zA-Z]{' + str(MIN_TOPIC_WORD_LEN) + r',}\b', text.lower())
        topics = {
            w for w in words
            if w not in STOPWORDS
        }
        return topics

    # ── Link following ────────────────────────────────────────────────────────

    def follow_links(
        self,
        seed_uris: List[str],
        depth:     int = 1,
    ) -> List[MemoryPage]:
        """
        Follow links from seed pages to discover related pages.

        Used by the indexer to surface pages that are referenced
        by currently relevant content.

        Args:
            seed_uris: Starting URIs.
            depth:     How many link hops to follow.

        Returns:
            Discovered pages (not including seeds).
        """
        visited    = set(seed_uris)
        discovered = []
        frontier   = list(seed_uris)

        for _ in range(depth):
            next_frontier = []
            for uri in frontier:
                linked_uris = self._web.get_linked_pages(uri, direction="both")
                for linked_uri in linked_uris:
                    if linked_uri not in visited:
                        visited.add(linked_uri)
                        page = self._web.get_page(linked_uri)
                        if page and page.status == STATUS_ACTIVE:
                            discovered.append(page)
                            next_frontier.append(linked_uri)
            frontier = next_frontier

        return discovered
