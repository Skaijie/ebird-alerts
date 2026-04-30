from json import load as jload, dump as jdump
from pickle import load as pload, dump as pdump
from os import path

def load_json(file_path, encode: str="utf-8"):
    if path.exists(file_path):
        with open(file_path, "r", encoding=encode) as f:
            data = jload(f)
        return data
    return []

def save_json(file_path, data, encode: str="utf-8"):
    with open(file_path, "w", encoding=encode) as f:
        jdump(data, f, indent=4)
    f.close()

def load_pkl(file_path):
    if path.exists(file_path):
        with open(file_path, 'rb') as f:
            loaded_pkl = pload(f)
        return loaded_pkl

def save_pkl(file_path, data):
    with open(file_path, 'wb') as file:
        pdump(data, file)
