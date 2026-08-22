from pathlib import Path

from tenderlens.ml.reranker import summarize_dataset, validate_reranker_dataset
from tenderlens.ml.synthetic_corpus import (
    CONFUSION_GROUPS,
    FACT_CATEGORIES,
    build_document_facts,
    build_reranker_examples,
    load_scenarios,
)

SCENARIO_PATH = Path("evals/synthetic_tender_corpus_v2.json")


def test_v2_corpus_has_document_level_splits_and_expected_scale() -> None:
    scenarios = load_scenarios(SCENARIO_PATH)
    examples = build_reranker_examples(scenarios)

    validate_reranker_dataset(examples)
    summary = summarize_dataset(examples)

    assert len(scenarios) == 24
    assert sum(scenario.pdf_sample for scenario in scenarios) == 12
    assert summary.query_count == 576
    assert summary.pair_count == 2_304
    assert summary.document_count == 24
    assert summary.split_queries == {"train": 384, "validation": 96, "test": 96}
    assert summary.languages == {"ru": 384, "en": 192}


def test_v2_corpus_is_deterministic() -> None:
    scenarios = load_scenarios(SCENARIO_PATH)

    first = build_reranker_examples(scenarios)
    second = build_reranker_examples(scenarios)

    assert first == second


def test_each_question_uses_three_semantically_confusing_negatives() -> None:
    examples = build_reranker_examples(load_scenarios(SCENARIO_PATH))

    for example in examples:
        assert len(example.negatives) == 3
        assert len(example.negative_categories) == 3
        assert set(example.negative_categories) == set(CONFUSION_GROUPS[example.category])


def test_document_facts_have_expected_pages_and_no_missing_categories() -> None:
    scenario = load_scenarios(SCENARIO_PATH)[0]
    facts = build_document_facts(scenario)

    assert {fact.category for fact in facts} == set(FACT_CATEGORIES)
    assert {fact.page_number for fact in facts} == {1, 2, 3}
    assert all(getattr(scenario, fact.category) in fact.passage for fact in facts)
