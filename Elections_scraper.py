"""
Elections_scraper: třetí projekt do Engeto Online Akademie Datový analytik s Pythonem
author: Romana Bělohoubková
email: romanabelohoubková@gmial.com
discord: Romana B.
"""

import argparse
import csv
import sys
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup


def zkontroluj_url(adresa):
    if not adresa.startswith(("http://", "https://")):
        raise ValueError(
            "Chyba: Zadaná adresa musí začínat na 'http://' nebo 'https://'."
        )
    if "volby.cz" not in adresa:
        raise ValueError(
            "Chyba: Adresa nevede na oficiální volební web 'volby.cz'."
        )
    if "ps32" not in adresa:
        raise ValueError(
            "Chyba: Adresa nevede na stránku se seznamem obcí "
            "(musí obsahovat 'ps32')."
        )
    return True


def zkontroluj_priponu_csv(soubor):
    if not soubor.endswith(".csv"):
        raise ValueError(
            "Chyba: Výstupní soubor musí mít příponu '.csv'."
        )


def nacti_obce(adresa):
    odpoved = requests.get(adresa)
    soup = BeautifulSoup(odpoved.text, 'html.parser')

    obce = {}
    for radek in soup.select("tr"):
        bunka_kod = radek.select_one("td.cislo")
        bunka_nazev = radek.select_one("td.overflow_name")

        if not bunka_kod or not bunka_nazev:
            continue

        try:
            kod = int(bunka_kod.get_text().strip())
            nazev = bunka_nazev.get_text().strip()
            obce[kod] = nazev
        except ValueError:
            continue

    return obce


def sestav_url_pro_obec(kod_obce, zakladni_url):
    parsed_url = urlparse(zakladni_url)
    parametry = parse_qs(parsed_url.query)

    jazyk = parametry.get("xjazyk", ["CZ"])[0]
    kraj = parametry.get("xkraj", [None])[0]
    vyber = parametry.get("xnumnuts", [None])[0]

    if not kraj or not vyber:
        print("Chyba: URL neobsahuje parametr xkraj nebo xnumnuts.")
        return None

    return (
        f"https://www.volby.cz/pls/ps2017nss/ps311?xjazyk={jazyk}" 
        f"&xkraj={kraj}&xobec={kod_obce}&xvyber={vyber}"
    )


def stahni_html_stranku(adresa):
    odpoved = requests.get(adresa)
    if odpoved.status_code != 200:
        print(
            f"Chyba: Nepodařilo se stáhnout data z adresy {adresa}. "
            f"HTTP {odpoved.status_code}"
        )
        return None
    return odpoved.text


def ziskej_data_pro_obec(kod_obce, zakladni_url):
    adresa = sestav_url_pro_obec(kod_obce, zakladni_url)
    if not adresa:
        return {}

    html = stahni_html_stranku(adresa)
    if not html:
        return {}

    soup = BeautifulSoup(html, 'html.parser')

    data = {
        "volici_v_seznamu": "N/A",
        "vydane_obalky": "N/A",
        "platne_hlasy": "N/A",
        "strany": {}
    }

    tabulka = soup.find('table', id='ps311_t1')
    if not tabulka:
        return data

    radky = tabulka.find_all('tr')
    if len(radky) <= 2:
        return data  # Na třetím řádku (index 2) obvykle začínají údaje o voličích a hlasech

    sloupce = radky[2].find_all('td')
    if len(sloupce) < 8:
        return data

    data["volici_v_seznamu"] = (
        sloupce[3].text.strip().replace("\xa0", "")
    )
    data["vydane_obalky"] = (
        sloupce[4].text.strip().replace("\xa0", "")
    )
    data["platne_hlasy"] = (
        sloupce[7].text.strip().replace("\xa0", "")
    )

    data["strany"] = extrahuj_vysledky_stran(soup)

    return data


def extrahuj_vysledky_stran(soup):
    vysledky = {}
    boxy = soup.find_all('div', class_='t2_470')

    for box in boxy:
        tabulky = box.find_all('table')
        for tabulka in tabulky:
            radky = tabulka.find_all('tr')[2:]
            for radek in radky:
                sloupce = radek.find_all('td')
                if len(sloupce) > 2:
                    nazev_strany = sloupce[1].text.strip()
                    pocet_hlasu = (
                        sloupce[2].text.strip().replace("\xa0", "")
                    )
                    if nazev_strany in vysledky:
                        vysledky[nazev_strany] = str(
                            int(vysledky[nazev_strany]) + int(pocet_hlasu)
                        )
                    else:
                        vysledky[nazev_strany] = pocet_hlasu

    return vysledky


def uloz_do_csv(data, vystupni_soubor):
    if not data:
        return

    hlavicka = [
        'Kód obce',
        'Název obce',
        'Voliči v seznamu',
        'Vydané obálky',
        'Platné hlasy'
    ]

    seznam_stran = sorted({
        strana
        for zaznam in data
        if zaznam["strany"]
        for strana in zaznam["strany"]
    })
    hlavicka.extend(seznam_stran)

    radky = [
        [
            zaznam["code"],
            zaznam["name"],
            zaznam["volici_v_seznamu"],
            zaznam["vydane_obalky"],
            zaznam["platne_hlasy"],
            *[
                zaznam["strany"].get(strana, "N/A")
                for strana in seznam_stran
            ]
        ]
        for zaznam in data
    ]

    with open(vystupni_soubor, mode='w', newline='', encoding='utf-8') as soubor:
        zapisovac = csv.writer(soubor)
        zapisovac.writerow(hlavicka)
        zapisovac.writerows(radky)


def hlavni():
    try:
        if len(sys.argv) != 3:
            raise ValueError(
                "Chyba: Skript vyžaduje zadání dvou argumentů v pořadí:\n"
                "    1) URL s výsledky voleb\n"
                "    2) Název výstupního souboru .csv"
            )

        parser = argparse.ArgumentParser(
            description="Stažení dat z volebního webu a uložení do CSV."
        )
        parser.add_argument(
            "url", type=str, help="URL územního celku"
        )
        parser.add_argument(
            "soubor", type=str, help="Název výstupního CSV souboru"
        )
        args = parser.parse_args()

        zkontroluj_url(args.url)
        zkontroluj_priponu_csv(args.soubor)

        print(f"STAHUJI DATA Z URL: {args.url}")

        obce = nacti_obce(args.url)
        if not obce:
            raise ValueError(
                "Chyba: Na zadané URL nebyly nalezeny žádné obce."
            )

        vsechna_data = []
        for kod, nazev in obce.items():
            data_obce = ziskej_data_pro_obec(kod, args.url)
            if not data_obce:
                print(
                    f"Upozornění: Nepodařilo se načíst data "
                    f"pro obec {kod} – {nazev}"
                )
                continue
            data_obce["code"] = kod
            data_obce["name"] = nazev
            vsechna_data.append(data_obce)

        if not vsechna_data:
            raise ValueError(
                "Chyba: Nepodařilo se stáhnout žádná data "
                "z jednotlivých obcí."
            )

        uloz_do_csv(vsechna_data, args.soubor)

        print(f"UKLÁDÁM DO SOUBORU: {args.soubor}")
        print("UKONČUJI Elections Scraper")

    except ValueError as e:
        print(f"\n{e}")
        print(
            "Oprava: Zkontrolujte správnost zadané URL nebo názvu výstupního "
            "souboru (musí mít příponu .csv)."
        )

    except Exception as e:
        print(f"\nNeočekávaná chyba: {e}")
        print(
            "Oprava: Ujistěte se, že máte připojení k internetu "
            "a že stránka existuje."
        )


if __name__ == "__main__":
    hlavni()

