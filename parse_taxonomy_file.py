from csv import DictReader
from species import Species, speciesStore
from json_handler import load_pkl, save_pkl
import os

def taxonomy_to_obj(from_taxo_file: str, to_species_file: str) -> speciesStore:
    species_dict = {}
    with open(from_taxo_file, newline="", encoding="utf-8") as f:
        for row in DictReader(f):
            species_code = row["SPECIES_CODE"]
            if species_code not in species_dict:
                species_dict[species_code] = Species(species_code, row["PRIMARY_COM_NAME"], row["SCI_NAME"], set())
            if (parent_species := row["REPORT_AS"]):
                species_dict[species_code].parent = parent_species
    
    save_pkl(to_species_file, species_dict)
    return species_dict

def main():
    taxonomy_to_obj("datasets\\eBird_taxonomy_v2025.csv", "datasets\\ebird_taxonomy.pkl")
    
if __name__ == "__main__":
    main()