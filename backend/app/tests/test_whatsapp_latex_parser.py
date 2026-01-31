from app.services.whatsapp.latex_parser import extract_latex, make_latex_cache_key


def test_extract_latex_blocks_and_inline():
    text = "Solve $$x^2=1$$ then \\(x=1\\)"
    blocks, plain = extract_latex(text)

    assert len(blocks) == 2
    assert blocks[0]["type"] == "block"
    assert blocks[0]["latex"] == "x^2=1"
    assert blocks[1]["type"] == "inline"
    assert blocks[1]["latex"] == "x=1"
    assert "[EQ_1]" in plain
    assert "[EQ_2]" in plain


def test_extract_latex_environment():
    text = "\\begin{align}a&=b\\\\c&=d\\end{align}"
    blocks, plain = extract_latex(text)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "block"
    assert "a&=b" in blocks[0]["latex"]
    assert "[EQ_1]" in plain


def test_cache_key_normalization():
    key1 = make_latex_cache_key("x  +   y", "katex", "webp", True)
    key2 = make_latex_cache_key("x + y", "katex", "webp", True)
    assert key1 == key2
