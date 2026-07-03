import os
import sys

# Make the flat script modules (config, dataset, model, evaluators) importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
