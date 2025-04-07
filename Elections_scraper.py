"""
Elections_scraper: třetí projekt do Engeto Online Akademie Datový analytik s Pythonem
author: Romana Bělohoubková
email: romanabelohoubkova@gmial.com
discord: Romana B.
"""

import argparse
import csv
import requests
from bs4 import BeautifulSoup

def get_locations(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    locations = {}
    rows = soup.select("tr") 
    for row in rows:
        code_cell = row.select_one("td.cislo") 
        name_cell = row.select_one("td.overflow_name")  
        if code_cell and name_cell:
            try:
                code = int(code_cell.get_text().strip())
                name = name_cell.get_text().strip()
                locations[code] = name
            except ValueError:
                continue
    return locations

def get_election_details_for_location(location_code):
    url = f"https://www.volby.cz/pls/ps2017nss/ps311?xjazyk=CZ&xkraj=8&xobec={location_code}&xvyber=5201"
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Chyba: Nepodařilo se stáhnout data pro lokalitu {location_code}. HTTP {response.status_code}")
        return {}

    soup = BeautifulSoup(response.text, 'html.parser')
    
    data = {
        "voliči_v_seznamu": "N/A",
        "vydane_obalky": "N/A",
        "platne_hlasy": "N/A",
        "strany": {}
    }

    table = soup.find('table', id='ps311_t1')
    if table:
        rows = table.find_all('tr')
        if len(rows) > 2:
            cols = rows[2].find_all('td')
            if len(cols) >= 8:
                data["voliči_v_seznamu"] = cols[3].text.strip().replace("\xa0", "")
                data["vydane_obalky"] = cols[4].text.strip().replace("\xa0", "")
                data["platne_hlasy"] = cols[7].text.strip().replace("\xa0", "")

    
    div_contents = soup.find_all('div', class_='t2_470')  # Najdeme všechny tabulky s výsledky stran
    for div_content in div_contents:
        party_tables = div_content.find_all('table')  
        for party_table in party_tables:
            rows = party_table.find_all('tr')[2:]  
            for row in rows:
                cols = row.find_all('td')
                if len(cols) > 2:
                    party_name = cols[1].text.strip()
                    party_votes = cols[2].text.strip().replace("\xa0", "")
                    if party_name in data["strany"]:
                        data["strany"][party_name] = str(int(data["strany"][party_name]) + int(party_votes))
                    else:
                        data["strany"][party_name] = party_votes

    return data

def save_to_csv(data, output_file):
    with open(output_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        header = ['Kód lokality', 'Název lokality', 'Voliči v seznamu', 'Vydané obálky', 'Platné hlasy']
        if data:
            party_names = sorted({party for d in data if d["strany"] for party in d["strany"]})
            header.extend(party_names)
        writer.writerow(header)
        
        for row in data:
            row_data = [row["code"], row["name"], row["voliči_v_seznamu"], row["vydane_obalky"], row["platne_hlasy"]]
            for party in party_names:
                row_data.append(row["strany"].get(party, "N/A"))
            writer.writerow(row_data)

def main():
    parser = argparse.ArgumentParser(description="Stažení dat z volebního webu a uložení do CSV.")
    parser.add_argument("url", type=str, help="URL územního celku")
    parser.add_argument("output_file", type=str, help="Název výstupního CSV souboru")
    args = parser.parse_args()
    
    print(f"STAHUJI DATA Z VYBRANÉHO URL: {args.url}")

    locations_data = get_locations(args.url)
    if not locations_data:
        print("Chyba: Data nebyla nalezena.")
        return
    
    all_data = []
    for code, name in locations_data.items():
        election_details = get_election_details_for_location(code)
        election_details["code"] = code
        election_details["name"] = name
        all_data.append(election_details)
    
    save_to_csv(all_data, args.output_file)

    print(f"UKLÁDÁM DO SOUBORU: {args.output_file}")
    print("UKONČUJI Elections Scraper")

if __name__ == "__main__":
    main()