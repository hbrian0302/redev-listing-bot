def test_margin_importable():
    import margin
    assert hasattr(margin, "decide")
