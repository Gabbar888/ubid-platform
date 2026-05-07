"""Smoke test the Kannada → Roman transliteration path."""
import sys
sys.path.insert(0, "/app/src")

from ubid.canonicalize.name_normalizer import (
    normalize, _transliterate_kannada, _is_likely_kannada,
)

cases = [
    "ಶರ್ಮಾ ಟ್ರೇಡರ್ಸ್",                     # Sharma Traders
    "ಎಂ ಎಸ್ ಕುಮಾರ್ ಎಂಜಿನಿಯರಿಂಗ್",          # M S Kumar Engineering
    "Sharma Traders Pvt Ltd",              # already Roman
    "M/s ಕುಮಾರ್ ಎಂಡ್ ಕೋ",                  # mixed Roman + Kannada
    "ಬೆಂಗಳೂರು ಮಿಲ್ಸ್",                      # Bangalore Mills
]

print("=" * 80)
print(f"{'Raw input':<32s}  {'Kannada?':<10s}  {'After transliteration':<32s}")
print("=" * 80)
for t in cases:
    is_kn = _is_likely_kannada(t)
    after = _transliterate_kannada(t) if is_kn else t
    print(f"{t:<32s}  {str(is_kn):<10s}  {after:<32s}")

print()
print("Full normalize() pipeline (what the scorer actually sees):")
print("-" * 80)
for t in cases:
    normalized, tokens, stripped = normalize(t)
    print(f"  Raw:        {t}")
    print(f"  Normalized: {normalized!r}")
    print(f"  Tokens:     {tokens}")
    print(f"  Stripped:   {stripped!r}")
    print()
