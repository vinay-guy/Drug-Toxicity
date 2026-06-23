import sys
sys.path.insert(0, 'src')
from mixture_analyzer import predict_single

# Test diverse chemicals (not just predefined ones)
test_smiles = [
    'CC(=O)Nc1ccc(O)cc1',  # Paracetamol
    'CC(C)Cc1ccc(C(C)C(O)=O)cc1',  # Ibuprofen
    'CN1CCC[C@H]1c1cccnc1',  # Nicotine
    'c1ccc2cc3ccccc3cc2c1',  # Anthracene
    'CC(C)(C)OC(=O)N=C=O',  # Boc-isocyanate
    'CC1=CC=C(C=C1)C(=O)O',  # Benzoic acid
    'C1=CC=C(C=C1)N',  # Aniline
    'CC(=O)OC1=CC=CC=C1C(=O)O',  # Aspirin
]

print('Testing diverse chemicals:')
for smi in test_smiles:
    result = predict_single(smi)
    print(f'  {smi[:35]:35} -> {result.label if result else "None"}')
