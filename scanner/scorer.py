import re

COMMON_ENGLISH = {
    "the","and","for","are","but","not","you","all","can","had","her","was","one",
    "our","out","has","have","been","some","them","than","that","this","very","were",
    "each","from","which","their","what","when","with","make","more","most","also",
    "over","into","such","only","other","about","after","then","there","would",
    "could","should","well","book","edition","volume","series","press","university",
    "oxford","cambridge","harvard","mit","wiley","addison","wesley","prentice",
    "hall","mcgraw","hill","springer","elsevier","north","holland","morgan",
    "kaufmann","freeman","company","inc","ltd","copyright","printed","rights",
    "reserved","first","second","third","fourth","fifth","sixth","seventh","eighth",
    "ninth","tenth","new","york","london","tokyo","singapore","sydney","toronto",
    "algorithms","applications","techniques","introduction","theory","analysis",
    "design","implementation","programming","network","networks","systems","data",
    "science","engineering","mathematics","physics","chemistry","biology","neural",
    "fuzzy","genetic","evolutionary","adaptive","control","signal","image",
    "processing","computer","vision","machine","learning","artificial","intelligence",
    "robotics","automation","information","communication","management","business",
    "economics","finance","accounting","marketing","guide","practical","quantitative",
    "qualitative","research","methods","statistics","probability","linear","algebra",
    "calculus","differential","equations","mechanics","thermodynamics","quantum",
    "electromagnetic","dynamics","functional","analysis","topology","geometry",
    "discrete","combinatorics","optimization","numerical","simulation",
    "architecture","organization","operating","systems","compiler","database",
}


def score_line(text: str, font_size: float, y_position: int, img_height: int) -> dict:
    words = text.split()
    if not words:
        return {"lexical": 0, "structural": 0, "combined": 0, "label": "garbage"}

    lexical = _lexical_score(words)
    structural = _structural_score(text, words, font_size, y_position, img_height)
    combined = lexical * 0.6 + structural * 0.4

    if combined < 0.3:
        label = "garbage"
    elif structural > 0.6:
        label = "title_like" if font_size > 0.7 else "author_like"
    else:
        label = "text"

    return {"lexical": lexical, "structural": structural, "combined": combined, "label": label}


def _lexical_score(words):
    if not words:
        return 0
    hits = 0
    total_vowels = 0
    total_consonants = 0
    for w in words:
        clean = re.sub(r"[^a-zA-Z]", "", w).lower()
        if not clean:
            continue
        if clean in COMMON_ENGLISH or len(clean) >= 5:
            hits += 1
        vowels = sum(1 for c in clean if c in "aeiou")
        cons = len(clean) - vowels
        total_vowels += vowels
        total_consonants += cons

    # Vowel ratio — garbage like "CRRA" has very few vowels
    total_letters = total_vowels + total_consonants
    vowel_ratio = total_vowels / max(total_letters, 1)

    dict_rate = hits / max(len(words), 1)

    score = dict_rate * 0.6
    if vowel_ratio > 0.15:
        score += 0.2
    if vowel_ratio > 0.25:
        score += 0.2

    return min(score, 1.0)


def _structural_score(text, words, font_size, y_position, img_height):
    score = 0.4  # base

    # Title-like: long, noun-heavy, few punctuation marks
    if len(text) > 20:
        score += 0.15
    if len(text) > 50:
        score += 0.1

    caps_ratio = sum(1 for w in words if w[0].isupper()) / max(len(words), 1)
    if caps_ratio > 0.6:
        score += 0.15

    punct_count = sum(1 for c in text if c in ".,:;!?")
    if punct_count <= 2:
        score += 0.1

    # Author-like: 2-4 capitalized tokens
    if 2 <= len(words) <= 5 and caps_ratio > 0.8:
        score += 0.1

    # Positional: books typically have title in upper portion
    relative_y = y_position / max(img_height, 1)
    if relative_y < 0.5:
        score += 0.1

    return min(score, 1.0)


def filter_lines(lines_data: list) -> list:
    """Filter a list of line dicts with keys: text, font_size, y, img_height.
    Returns only lines where combined score > 0.35 and label != 'garbage'."""
    filtered = []
    for line in lines_data:
        result = score_line(
            text=line.get("text", ""),
            font_size=line.get("font_size", 0),
            y_position=line.get("y", 0),
            img_height=line.get("img_height", 1),
        )
        if result["combined"] > 0.35 and result["label"] != "garbage":
            line["_scores"] = result
            filtered.append(line)
    return filtered
