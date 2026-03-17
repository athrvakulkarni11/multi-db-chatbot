"""
Text Processing Utilities
"""
import re


def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters but keep punctuation
    text = re.sub(r'[^\w\s.,!?;:\'"()\-\n]', '', text)
    # Normalize line breaks
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """Truncate text to max length at word boundary."""
    if len(text) <= max_length:
        return text
    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(' ')
    if last_space > max_length // 2:
        truncated = truncated[:last_space]
    return truncated + suffix


def extract_keywords(text: str, top_k: int = 10) -> list[str]:
    """Extract important keywords from text using simple TF approach."""
    # Common stop words
    stop_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'shall', 'can', 'need', 'dare', 'ought',
        'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
        'as', 'into', 'through', 'during', 'before', 'after', 'above',
        'below', 'between', 'out', 'off', 'over', 'under', 'again',
        'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why',
        'how', 'all', 'both', 'each', 'few', 'more', 'most', 'other',
        'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so',
        'than', 'too', 'very', 'just', 'because', 'but', 'and', 'or',
        'if', 'while', 'this', 'that', 'these', 'those', 'i', 'me', 'my',
        'we', 'our', 'you', 'your', 'he', 'him', 'his', 'she', 'her',
        'it', 'its', 'they', 'them', 'their', 'what', 'which', 'who'
    }

    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    word_counts = {}
    for word in words:
        if word not in stop_words:
            word_counts[word] = word_counts.get(word, 0) + 1

    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in sorted_words[:top_k]]


def count_tokens_approx(text: str) -> int:
    """Approximate token count (roughly 4 chars per token for English)."""
    return len(text) // 4
