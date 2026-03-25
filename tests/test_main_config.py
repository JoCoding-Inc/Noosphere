def test_simconfig_defaults():
    from backend.main import SimConfig
    cfg = SimConfig(input_text="hello")
    assert cfg.input_text == "hello"
    assert cfg.num_rounds == 8
    assert cfg.max_agents == 30
