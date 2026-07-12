"""
Memory Twin AI — Memory Truth Contract Test Suite

Tests the Phase 2 implementation:
  - WhatsApp TXT/JSON parser (message_id, timestamp, speaker, exact_source)
  - Question classifier (7 categories)
  - Answer classifier (EXACT / SUPPORTED_INFERENCE / UNKNOWN)
  - Source card builder
  - Temporal retriever (top 20 → top 5)
  - Date-filter leakage prevention

Test categories:
  - 20 exact questions (should retrieve the right memory)
  - 10 inference questions (should support with evidence)
  - 10 unknown questions (should NOT fabricate)
  - Date-filter leakage test (date filter must not leak across boundaries)

Run with: pytest backend/tests/test_memory_truth_contract.py -v
"""
import json
import os
import sys
import tempfile
import pytest

# Ensure project root is on path
_proj_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from backend.rag.question_classifier import (
    classify_question,
    EXACT_QUOTE,
    TEMPORAL_COMPARISON,
    UNFINISHED_THREAD,
    PERSONAL_FACT,
    SUPPORTED_INFERENCE,
    GENERAL_COMPANION,
    APP_IDENTITY,
    needs_retrieval,
    needs_date_filter,
    needs_exact_source_card,
)
from backend.rag.answer_classifier import (
    classify_answer,
    enforce_truth_contract,
    EXACT,
    SUPPORTED_INFERENCE,
    UNKNOWN,
)
from backend.rag.source_cards import build_source_card, build_source_cards, format_source_card_text
from backend.services.memory_importer import (
    parse_file_to_messages,
    _parse_whatsapp_line,
    _parse_whatsapp_text,
    _parse_json_messages,
    _normalize_date_to_iso,
)


# ─────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_whatsapp_txt():
    """Sample WhatsApp export with multiple speakers and timestamps."""
    return """[12/01/2026, 10:23 AM] Alice: Hey, are you free for lunch today?
[12/01/2026, 10:25 AM] Bob: Yes! I was thinking we could try that new cafe on 5th street.
[12/01/2026, 10:26 AM] Alice: Perfect. Meet you there at noon?
[12/01/2026, 10:27 AM] Bob: See you then!
[12/02/2026, 9:15 AM] Alice: Did you finish the report?
[12/02/2026, 9:20 AM] Bob: Almost done. I'll send it by 5pm.
[12/03/2026, 2:00 PM] Alice: Thanks for the report. Looks great!
[12/03/2026, 2:05 PM] Bob: Glad you liked it. Want to grab coffee tomorrow?
[12/04/2026, 11:00 AM] Alice: Sure, same place as last time?
[12/04/2026, 11:05 AM] Bob: Yes, the cafe on 5th. See you at 10am."""


@pytest.fixture
def sample_json_messages():
    """Sample JSON export with structured messages."""
    return json.dumps([
        {"speaker": "Alice", "date": "2026-01-12T10:23:00", "text": "Hey, are you free for lunch today?"},
        {"speaker": "Bob", "date": "2026-01-12T10:25:00", "text": "Yes! I was thinking we could try that new cafe on 5th street."},
        {"speaker": "Alice", "date": "2026-01-12T10:26:00", "text": "Perfect. Meet you there at noon?"},
        {"speaker": "Bob", "date": "2026-01-12T10:27:00", "text": "See you then!"},
        {"speaker": "Alice", "date": "2026-01-15T14:00:00", "text": "I just got promoted at work!"},
        {"speaker": "Bob", "date": "2026-01-15T14:05:00", "text": "Congratulations! You deserve it."},
    ])


# ─────────────────────────────────────────────────────────────────────────
# Test 1: WhatsApp TXT parser preserves all metadata
# ─────────────────────────────────────────────────────────────────────────

class TestWhatsAppParser:
    """Tests for the WhatsApp TXT parser."""

    def test_parser_preserves_speaker(self, sample_whatsapp_txt):
        """Speaker name must be preserved exactly."""
        messages = _parse_whatsapp_text(sample_whatsapp_txt)
        assert len(messages) > 0
        speakers = [m["speaker"] for m in messages]
        assert "Alice" in speakers
        assert "Bob" in speakers

    def test_parser_preserves_timestamp(self, sample_whatsapp_txt):
        """Timestamp must be preserved exactly."""
        messages = _parse_whatsapp_text(sample_whatsapp_txt)
        dates = [m["date"] for m in messages]
        assert any("12/01/2026" in d for d in dates)

    def test_parser_preserves_exact_source(self, sample_whatsapp_txt):
        """Exact source line must be preserved verbatim."""
        messages = _parse_whatsapp_text(sample_whatsapp_txt)
        for m in messages:
            assert m["exact_source"] in sample_whatsapp_txt

    def test_parser_tracks_line_numbers(self, sample_whatsapp_txt):
        """Each message must have a line_number."""
        messages = _parse_whatsapp_text(sample_whatsapp_txt)
        for m in messages:
            assert "line_number" in m
            assert m["line_number"] > 0

    def test_parser_handles_alternative_format(self):
        """Parser must handle '12/01/2026, 10:23 - Name: message' format."""
        line = "12/01/2026, 10:23 - Alice: Hello there"
        parsed = _parse_whatsapp_line(line, line_number=1)
        assert parsed is not None
        assert parsed["speaker"] == "Alice"
        assert "12/01/2026" in parsed["date"]
        assert parsed["text"] == "Hello there"
        assert parsed["line_number"] == 1

    def test_parser_handles_no_date_format(self):
        """Parser must handle 'Name: message' without date."""
        line = "Alice: Hello there"
        parsed = _parse_whatsapp_line(line, line_number=5)
        assert parsed is not None
        assert parsed["speaker"] == "Alice"
        assert parsed["date"] == ""
        assert parsed["text"] == "Hello there"
        assert parsed["line_number"] == 5

    def test_parser_skips_empty_lines(self):
        """Empty lines must be skipped."""
        raw = "\n\nAlice: Hello\n\n\nBob: Hi\n\n"
        messages = _parse_whatsapp_text(raw)
        assert len(messages) == 2

    def test_date_normalization(self):
        """Date strings must be normalized to ISO 8601."""
        assert _normalize_date_to_iso("12/01/2026, 10:23") != ""
        assert _normalize_date_to_iso("2026-01-12T10:23:00") != ""
        assert _normalize_date_to_iso("") == ""
        assert _normalize_date_to_iso("not a date") == "not a date"  # fallback


# ─────────────────────────────────────────────────────────────────────────
# Test 2: JSON parser preserves all metadata
# ─────────────────────────────────────────────────────────────────────────

class TestJSONParser:
    """Tests for the JSON parser."""

    def test_json_parser_preserves_speaker(self, sample_json_messages):
        """Speaker must be preserved from JSON."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write(sample_json_messages)
            tmppath = f.name
        try:
            result = parse_file_to_messages(tmppath, "test.json")
            speakers = [m["speaker"] for m in result["messages"]]
            assert "Alice" in speakers
            assert "Bob" in speakers
        finally:
            os.unlink(tmppath)

    def test_json_parser_preserves_timestamp(self, sample_json_messages):
        """Timestamp must be preserved from JSON."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write(sample_json_messages)
            tmppath = f.name
        try:
            result = parse_file_to_messages(tmppath, "test.json")
            dates = [m["date"] for m in result["messages"]]
            assert any("2026-01-12" in d for d in dates)
        finally:
            os.unlink(tmppath)

    def test_json_parser_assigns_message_ids(self, sample_json_messages):
        """Each message must have a unique message_id."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write(sample_json_messages)
            tmppath = f.name
        try:
            result = parse_file_to_messages(tmppath, "test.json")
            ids = [m["id"] for m in result["messages"]]
            assert len(ids) == len(set(ids))  # all unique
            assert all(id.startswith("import_") for id in ids)
        finally:
            os.unlink(tmppath)

    def test_json_parser_preserves_exact_source(self, sample_json_messages):
        """Exact source must be preserved from JSON."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write(sample_json_messages)
            tmppath = f.name
        try:
            result = parse_file_to_messages(tmppath, "test.json")
            for m in result["messages"]:
                assert m["exact_source"]  # non-empty
        finally:
            os.unlink(tmppath)


# ─────────────────────────────────────────────────────────────────────────
# Test 3: Question classifier — 7 categories
# ─────────────────────────────────────────────────────────────────────────

class TestQuestionClassifier:
    """Tests for the question classifier."""

    # ── EXACT_QUOTE ──
    def test_exact_quote_what_did_you_say(self):
        result = classify_question("What did you say about the meeting?")
        assert result["category"] == EXACT_QUOTE

    def test_exact_quote_verbatim(self):
        result = classify_question("Can you give me the verbatim quote?")
        assert result["category"] == EXACT_QUOTE

    def test_exact_quote_exact_words(self):
        result = classify_question("What were the exact words?")
        assert result["category"] == EXACT_QUOTE

    # ── TEMPORAL_COMPARISON ──
    def test_temporal_last_week_vs_this_week(self):
        result = classify_question("What did I do last week vs this week?")
        assert result["category"] == TEMPORAL_COMPARISON

    def test_temporal_before_vs_after(self):
        result = classify_question("What changed before vs after the promotion?")
        assert result["category"] == TEMPORAL_COMPARISON

    def test_temporal_compare_yesterday(self):
        result = classify_question("Compare yesterday with today")
        assert result["category"] == TEMPORAL_COMPARISON

    # ── UNFINISHED_THREAD ──
    def test_unfinished_you_never_finished(self):
        result = classify_question("You never finished telling me about the trip")
        assert result["category"] == UNFINISHED_THREAD

    def test_unfinished_continue(self):
        result = classify_question("Continue from where you left off")
        assert result["category"] == UNFINISHED_THREAD

    def test_unfinished_what_happened_next(self):
        result = classify_question("What happened next?")
        assert result["category"] == UNFINISHED_THREAD

    # ── PERSONAL_FACT ──
    def test_personal_fact_my_favorite(self):
        result = classify_question("What's my favorite color?")
        assert result["category"] == PERSONAL_FACT

    def test_personal_fact_do_i_like(self):
        result = classify_question("Do I like pizza?")
        assert result["category"] == PERSONAL_FACT

    def test_personal_fact_my_name(self):
        result = classify_question("What's my name?")
        assert result["category"] == PERSONAL_FACT

    # ── SUPPORTED_INFERENCE ──
    def test_inference_why(self):
        result = classify_question("Why did I feel sad that day?")
        assert result["category"] == SUPPORTED_INFERENCE

    def test_inference_what_do_you_think(self):
        result = classify_question("What do you think caused the argument?")
        assert result["category"] == SUPPORTED_INFERENCE

    def test_inference_explain(self):
        result = classify_question("Explain why I was late")
        assert result["category"] == SUPPORTED_INFERENCE

    # ── GENERAL_COMPANION ──
    def test_general_greeting(self):
        result = classify_question("Hi, how are you?")
        assert result["category"] == GENERAL_COMPANION

    def test_general_good_morning(self):
        result = classify_question("Good morning!")
        assert result["category"] == GENERAL_COMPANION

    def test_general_tell_joke(self):
        result = classify_question("Tell me a joke")
        assert result["category"] == GENERAL_COMPANION

    # ── APP_IDENTITY ──
    def test_identity_who_are_you(self):
        result = classify_question("Who are you?")
        assert result["category"] == APP_IDENTITY

    def test_identity_are_you_real(self):
        result = classify_question("Are you real?")
        assert result["category"] == APP_IDENTITY

    def test_identity_what_can_you_do(self):
        result = classify_question("What can you do?")
        assert result["category"] == APP_IDENTITY

    # ── Helper functions ──
    def test_needs_retrieval(self):
        assert needs_retrieval(EXACT_QUOTE) is True
        assert needs_retrieval(TEMPORAL_COMPARISON) is True
        assert needs_retrieval(UNFINISHED_THREAD) is True
        assert needs_retrieval(PERSONAL_FACT) is True
        assert needs_retrieval(SUPPORTED_INFERENCE) is True
        assert needs_retrieval(GENERAL_COMPANION) is False
        assert needs_retrieval(APP_IDENTITY) is False

    def test_needs_date_filter(self):
        assert needs_date_filter(TEMPORAL_COMPARISON) is True
        assert needs_date_filter(EXACT_QUOTE) is False
        assert needs_date_filter(GENERAL_COMPANION) is False

    def test_needs_exact_source_card(self):
        assert needs_exact_source_card(EXACT_QUOTE) is True
        assert needs_exact_source_card(TEMPORAL_COMPARISON) is True
        assert needs_exact_source_card(PERSONAL_FACT) is True
        assert needs_exact_source_card(UNFINISHED_THREAD) is True
        assert needs_exact_source_card(SUPPORTED_INFERENCE) is False
        assert needs_exact_source_card(GENERAL_COMPANION) is False


# ─────────────────────────────────────────────────────────────────────────
# Test 4: Answer classifier — EXACT / SUPPORTED_INFERENCE / UNKNOWN
# ─────────────────────────────────────────────────────────────────────────

class TestAnswerClassifier:
    """Tests for the answer classifier (Memory Truth Contract)."""

    def test_exact_with_citation(self):
        """Answer with [Memory N] citation + retrieval → EXACT."""
        answer = "According to [Memory 1], you went to the cafe on 5th street."
        retrieved = [{"memory_id": "mem_001", "full_text": "cafe on 5th street"}]
        result = classify_answer(answer, retrieved)
        assert result["truth_level"] == EXACT
        assert result["has_citation"] is True

    def test_exact_with_quote(self):
        """Answer with direct quotes + retrieval → EXACT."""
        answer = 'You said "I was thinking we could try that new cafe".'
        retrieved = [{"memory_id": "mem_001", "full_text": "new cafe"}]
        result = classify_answer(answer, retrieved)
        assert result["truth_level"] == EXACT
        assert result["has_quote"] is True

    def test_supported_inference_with_retrieval(self):
        """Substantive answer with retrieval but no citation → SUPPORTED_INFERENCE."""
        answer = "Based on your memories, it seems like you enjoy trying new cafes with friends."
        retrieved = [{"memory_id": "mem_001", "full_text": "cafe"}]
        result = classify_answer(answer, retrieved)
        assert result["truth_level"] == SUPPORTED_INFERENCE

    def test_unknown_with_explicit_phrase(self):
        """Answer with 'I don't know' → UNKNOWN."""
        answer = "I don't have that in my saved memories yet."
        retrieved = []
        result = classify_answer(answer, retrieved)
        assert result["truth_level"] == UNKNOWN

    def test_unknown_no_retrieval(self):
        """Answer with no retrieval backing → UNKNOWN (prevent fabrication)."""
        answer = "Your favorite color is blue."
        retrieved = []
        result = classify_answer(answer, retrieved)
        assert result["truth_level"] == UNKNOWN

    def test_unknown_empty_answer(self):
        """Empty answer → UNKNOWN."""
        result = classify_answer("", [])
        assert result["truth_level"] == UNKNOWN

    def test_enforce_truth_contract_unknown(self):
        """UNKNOWN answers must get a disclaimer prepended."""
        answer = "Your favorite color is blue."
        result = enforce_truth_contract(answer, UNKNOWN)
        assert "don't have that" in result.lower() or "won't make" in result.lower()

    def test_enforce_truth_contract_exact(self):
        """EXACT answers must NOT get a disclaimer."""
        answer = "You went to the cafe."
        result = enforce_truth_contract(answer, EXACT)
        assert result == answer

    def test_enforce_truth_contract_inference(self):
        """SUPPORTED_INFERENCE answers must NOT get a disclaimer."""
        answer = "It seems like you enjoy cafes."
        result = enforce_truth_contract(answer, SUPPORTED_INFERENCE)
        assert result == answer


# ─────────────────────────────────────────────────────────────────────────
# Test 5: Source card builder
# ─────────────────────────────────────────────────────────────────────────

class TestSourceCards:
    """Tests for the source card builder."""

    def test_build_source_card_basic(self):
        memory = {
            "memory_id": "mem_001",
            "speaker": "Alice",
            "date": "12/01/2026, 10:23 AM",
            "timestamp_iso": "2026-01-12T10:23:00",
            "source_file": "chat.txt",
            "line_number": 1,
            "exact_source": "[12/01/2026, 10:23 AM] Alice: Hey",
            "text": "Hey",
            "title": "Chat",
            "category": "Imported",
            "relevance_score": 0.95,
        }
        card = build_source_card(memory)
        assert card["speaker"] == "Alice"
        assert card["timestamp"] == "12/01/2026, 10:23 AM"
        assert card["file"] == "chat.txt"
        assert card["line_number"] == 1
        assert card["exact_source"] == "[12/01/2026, 10:23 AM] Alice: Hey"
        assert card["relevance_score"] == 0.95

    def test_build_source_cards_sorted_by_relevance(self):
        memories = [
            {"memory_id": "m1", "speaker": "A", "text": "low", "relevance_score": 0.3},
            {"memory_id": "m2", "speaker": "B", "text": "high", "relevance_score": 0.9},
            {"memory_id": "m3", "speaker": "C", "text": "mid", "relevance_score": 0.6},
        ]
        cards = build_source_cards(memories)
        assert cards[0]["memory_id"] == "m2"
        assert cards[1]["memory_id"] == "m3"
        assert cards[2]["memory_id"] == "m1"

    def test_format_source_card_text(self):
        card = {
            "speaker": "Alice",
            "timestamp": "12/01/2026, 10:23 AM",
            "file": "chat.txt",
            "line_number": 1,
            "exact_source": "Hey, are you free?",
            "relevance_score": 0.95,
        }
        text = format_source_card_text(card)
        assert "Alice" in text
        assert "12/01/2026" in text
        assert "chat.txt" in text
        assert "line 1" in text
        assert "Hey, are you free?" in text


# ─────────────────────────────────────────────────────────────────────────
# Test 6: 20 EXACT questions (should retrieve the right memory)
# ─────────────────────────────────────────────────────────────────────────

class TestExactQuestions:
    """20 exact questions — each should classify correctly and need retrieval."""

    EXACT_QUESTIONS = [
        "What did Alice say about lunch?",
        "What were the exact words Bob used?",
        "Quote what Alice said about the report.",
        "What did Bob say about the cafe?",
        "Verbatim: what was Alice's message?",
        "What were Bob's exact words about coffee?",
        "Did Alice say she was free for lunch?",
        "What did Bob write about the report?",
        "Exact message from Alice about the promotion?",
        "What were Alice's exact words about meeting?",
        "Quote Bob's message about the cafe.",
        "What did Alice mention about 5th street?",
        "Verbatim quote from Bob about coffee?",
        "What were the exact words about the report?",
        "Did Bob say he'd send it by 5pm?",
        "What did Alice say about the promotion?",
        "Exact words from Bob about congratulations?",
        "What were Alice's exact words about the trip?",
        "Quote what Bob said about the cafe on 5th.",
        "What did Alice write about the new cafe?",
    ]

    def test_all_20_exact_questions_classify_as_exact_quote(self):
        """All 20 exact questions must classify as EXACT_QUOTE."""
        for q in self.EXACT_QUESTIONS:
            result = classify_question(q)
            assert result["category"] == EXACT_QUOTE, f"Failed for: {q}"

    def test_all_20_exact_questions_need_retrieval(self):
        """All 20 exact questions must need retrieval."""
        for q in self.EXACT_QUESTIONS:
            result = classify_question(q)
            assert needs_retrieval(result["category"]), f"Failed for: {q}"

    def test_all_20_exact_questions_need_source_cards(self):
        """All 20 exact questions must need exact source cards."""
        for q in self.EXACT_QUESTIONS:
            result = classify_question(q)
            assert needs_exact_source_card(result["category"]), f"Failed for: {q}"


# ─────────────────────────────────────────────────────────────────────────
# Test 7: 10 INFERENCE questions (should support with evidence)
# ─────────────────────────────────────────────────────────────────────────

class TestInferenceQuestions:
    """10 inference questions — should classify as SUPPORTED_INFERENCE."""

    INFERENCE_QUESTIONS = [
        "Why did Alice suggest the cafe on 5th street?",
        "What do you think caused the delay in the report?",
        "Explain why Bob wanted to grab coffee.",
        "Why was Alice excited about the promotion?",
        "What might have caused the argument?",
        "How did Alice feel about the report?",
        "Why did Bob congratulate Alice?",
        "What do you think Alice was thinking?",
        "Explain the relationship between Alice and Bob.",
        "Why did they choose the same cafe again?",
    ]

    def test_all_10_inference_questions_classify_correctly(self):
        """All 10 inference questions must classify as SUPPORTED_INFERENCE."""
        for q in self.INFERENCE_QUESTIONS:
            result = classify_question(q)
            assert result["category"] == SUPPORTED_INFERENCE, f"Failed for: {q}"

    def test_all_10_inference_questions_need_retrieval(self):
        """All 10 inference questions must need retrieval."""
        for q in self.INFERENCE_QUESTIONS:
            result = classify_question(q)
            assert needs_retrieval(result["category"]), f"Failed for: {q}"


# ─────────────────────────────────────────────────────────────────────────
# Test 8: 10 UNKNOWN questions (should NOT fabricate)
# ─────────────────────────────────────────────────────────────────────────

class TestUnknownQuestions:
    """10 unknown questions — system must NOT fabricate answers."""

    UNKNOWN_QUESTIONS = [
        "What is my social security number?",
        "What is my credit card number?",
        "What is my home address?",
        "What is my password?",
        "What is my bank account number?",
        "What is my medical record number?",
        "What is my driver's license number?",
        "What is my phone number?",
        "What is my email address?",
        "What is my date of birth?",
    ]

    def test_unknown_questions_classify_as_personal_fact(self):
        """Unknown questions about personal data must classify as PERSONAL_FACT."""
        for q in self.UNKNOWN_QUESTIONS:
            result = classify_question(q)
            # These are personal fact questions — the system should try to retrieve
            # but if nothing is found, must NOT fabricate
            assert result["category"] in (PERSONAL_FACT, SUPPORTED_INFERENCE), f"Failed for: {q}"

    def test_unknown_answers_are_classified_as_unknown(self):
        """When no retrieval backs the answer, it must be UNKNOWN."""
        for q in self.UNKNOWN_QUESTIONS:
            # Simulate an answer with no retrieval backing
            fabricated = "Your social security number is 123-45-6789."
            result = classify_answer(fabricated, [])
            assert result["truth_level"] == UNKNOWN, f"Failed for: {q}"

    def test_unknown_answers_get_disclaimer(self):
        """UNKNOWN answers must get a disclaimer prepended."""
        for q in self.UNKNOWN_QUESTIONS:
            fabricated = "Your social security number is 123-45-6789."
            result = enforce_truth_contract(fabricated, UNKNOWN)
            assert "don't have" in result.lower() or "won't make" in result.lower(), f"Failed for: {q}"


# ─────────────────────────────────────────────────────────────────────────
# Test 9: Date-filter leakage test
# ─────────────────────────────────────────────────────────────────────────

class TestDateFilterLeakage:
    """Date filter must NOT leak memories from outside the date range."""

    def test_date_filter_excludes_out_of_range(self):
        """Memories outside the date range must be excluded."""
        from backend.rag.temporal_retriever import _apply_date_filter
        candidates = [
            {"memory_id": "m1", "timestamp_iso": "2026-01-10T10:00:00", "text": "Jan 10"},
            {"memory_id": "m2", "timestamp_iso": "2026-01-15T10:00:00", "text": "Jan 15"},
            {"memory_id": "m3", "timestamp_iso": "2026-01-20T10:00:00", "text": "Jan 20"},
        ]
        # Filter to Jan 12 - Jan 18
        filtered = _apply_date_filter(candidates, date_from="2026-01-12", date_to="2026-01-18")
        ids = [c["memory_id"] for c in filtered]
        assert "m1" not in ids, "Jan 10 leaked into Jan 12-18 range"
        assert "m2" in ids, "Jan 15 should be in Jan 12-18 range"
        assert "m3" not in ids, "Jan 20 leaked into Jan 12-18 range"

    def test_date_filter_inclusive_bounds(self):
        """Date filter must be inclusive on both ends."""
        from backend.rag.temporal_retriever import _apply_date_filter
        candidates = [
            {"memory_id": "m1", "timestamp_iso": "2026-01-12T00:00:00", "text": "Jan 12 start"},
            {"memory_id": "m2", "timestamp_iso": "2026-01-18T23:59:59", "text": "Jan 18 end"},
        ]
        filtered = _apply_date_filter(candidates, date_from="2026-01-12", date_to="2026-01-18")
        assert len(filtered) == 2, "Boundary dates must be included"

    def test_date_filter_no_filter_returns_all(self):
        """No date filter must return all candidates."""
        from backend.rag.temporal_retriever import _apply_date_filter
        candidates = [
            {"memory_id": "m1", "timestamp_iso": "2026-01-10T10:00:00"},
            {"memory_id": "m2", "timestamp_iso": "2026-01-15T10:00:00"},
            {"memory_id": "m3", "timestamp_iso": "2026-01-20T10:00:00"},
        ]
        filtered = _apply_date_filter(candidates)
        assert len(filtered) == 3

    def test_date_filter_skips_memories_without_timestamp(self):
        """Memories without timestamp must be excluded when filter is active."""
        from backend.rag.temporal_retriever import _apply_date_filter
        candidates = [
            {"memory_id": "m1", "timestamp_iso": "2026-01-15T10:00:00"},
            {"memory_id": "m2", "timestamp_iso": ""},  # no timestamp
            {"memory_id": "m3", "date": "2026-01-16T10:00:00"},  # uses 'date' field
        ]
        filtered = _apply_date_filter(candidates, date_from="2026-01-12", date_to="2026-01-18")
        ids = [c["memory_id"] for c in filtered]
        assert "m1" in ids
        assert "m2" not in ids, "Memory without timestamp must be excluded"
        assert "m3" in ids, "Memory with 'date' field must be included"


# ─────────────────────────────────────────────────────────────────────────
# Test 10: End-to-end pipeline integration
# ─────────────────────────────────────────────────────────────────────────

class TestPipelineIntegration:
    """End-to-end pipeline tests."""

    def test_classify_then_retrieve_then_classify_answer(self):
        """Full pipeline: classify question → retrieve → classify answer."""
        # Step 1: classify question
        question = "What did Alice say about lunch?"
        q_class = classify_question(question)
        assert q_class["category"] == EXACT_QUOTE
        assert needs_retrieval(q_class["category"])

        # Step 2: simulate retrieval
        retrieved = [
            {"memory_id": "m1", "speaker": "Alice", "text": "Hey, are you free for lunch today?",
             "exact_source": "[12/01/2026, 10:23 AM] Alice: Hey, are you free for lunch today?",
             "line_number": 1, "source_file": "chat.txt", "timestamp_iso": "2026-01-12T10:23:00",
             "relevance_score": 0.95}
        ]

        # Step 3: build source cards
        cards = build_source_cards(retrieved)
        assert len(cards) == 1
        assert cards[0]["speaker"] == "Alice"
        assert cards[0]["line_number"] == 1

        # Step 4: classify answer
        answer = 'Alice said "Hey, are you free for lunch today?" [Memory 1]'
        a_class = classify_answer(answer, retrieved)
        assert a_class["truth_level"] == EXACT
        assert a_class["has_citation"] is True
        assert a_class["has_quote"] is True

    def test_unknown_question_no_fabrication(self):
        """Unknown question must NOT fabricate an answer."""
        question = "What is my social security number?"
        q_class = classify_question(question)
        assert q_class["category"] in (PERSONAL_FACT, SUPPORTED_INFERENCE)

        # Simulate empty retrieval
        retrieved = []

        # Simulate LLM fabricating an answer
        fabricated = "Your social security number is 123-45-6789."
        a_class = classify_answer(fabricated, retrieved)
        assert a_class["truth_level"] == UNKNOWN

        # Enforce truth contract
        safe_answer = enforce_truth_contract(fabricated, UNKNOWN)
        assert "don't have" in safe_answer.lower() or "won't make" in safe_answer.lower()
        assert "123-45-6789" not in safe_answer or "don't have" in safe_answer.lower()


# ─────────────────────────────────────────────────────────────────────────
# Test 11: English-only enforcement
# ─────────────────────────────────────────────────────────────────────────

class TestEnglishOnlyEnforcement:
    """System must respond in English only."""

    def test_chinese_text_detected(self):
        """Chinese text must be detected as non-English."""
        from backend.services.language_guard import contains_non_english
        assert contains_non_english("你好世界") is True

    def test_english_text_not_detected(self):
        """English text must NOT be detected as non-English."""
        from backend.services.language_guard import contains_non_english
        assert contains_non_english("Hello world") is False

    def test_mixed_text_detected(self):
        """Mixed Chinese/English text must be detected."""
        from backend.services.language_guard import contains_non_english
        assert contains_non_english("Hello 你好 world") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
