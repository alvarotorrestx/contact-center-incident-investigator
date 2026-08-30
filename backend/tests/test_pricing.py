from incident_investigator.persistence import estimate_gpt_5_6_sol_cost


def test_cost_estimate_accounts_for_cached_and_cache_write_tokens() -> None:
    usage = {
        "input_tokens": 1_000_000,
        "input_tokens_details": {
            "cached_tokens": 200_000,
            "cache_write_tokens": 300_000,
        },
        "output_tokens": 100_000,
    }

    assert estimate_gpt_5_6_sol_cost(usage) == 5.58
