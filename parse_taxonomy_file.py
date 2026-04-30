from csv import DictReader
from species import Species
from json_handler import save_pkl

def taxonomy_to_obj(taxo_file: str) -> dict[str, Species]:
    species_dict: dict[str, Species] = {}
    with open(taxo_file, newline="", encoding="utf-8") as f:
        for row in DictReader(f):
            species_code = row["SPECIES_CODE"]
            if species_code not in species_dict:
                species_dict[species_code] = Species(species_code, row["PRIMARY_COM_NAME"], row["SCI_NAME"], set())
            if (parent_species := row["REPORT_AS"]):
                species_dict[species_code].parent = parent_species

    save_pkl("datasets\\ebird_taxonomy.pkl", species_dict)
    return species_dict

def main():
    taxonomy_to_obj("datasets\\eBird_taxonomy_v2025.csv")
    
if __name__ == "__main__":
    main()