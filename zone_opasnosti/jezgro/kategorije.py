IZVORI_HAZARDA = [
    {
        "id": "pumpa",
        "naziv": "Benzinska pumpa",
        "tagovi": [{"amenity": "fuel"}],
        "radijus": 100,
    },
    {
        "id": "postrojenje",
        "naziv": "Industrijsko postrojenje",
        "tagovi": [{"man_made": "works"}],
        "radijus": 300,
    },
    {
        "id": "industrijska_zona",
        "naziv": "Industrijska zona",
        "tagovi": [{"landuse": "industrial"}],
        "radijus": 300,
    },
    {
        "id": "trafostanica",
        "naziv": "Trafostanica",
        "tagovi": [{"power": "substation"}],
        "radijus": 50,
    },
    {
        "id": "elektrana",
        "naziv": "Elektrana / toplana",
        "tagovi": [{"power": "plant"}],
        "radijus": 300,
    },
    {
        "id": "skladiste_goriva",
        "naziv": "Skladiste goriva",
        "tagovi": [{"man_made": "storage_tank", "content": "fuel"}],
        "radijus": 300,
    },
    {
        "id": "zel_stanica",
        "naziv": "Zeleznicka stanica",
        "tagovi": [{"railway": "station"}],
        "radijus": 200,
    },
]

RANJIVI_OBJEKTI = [
    {
        "id": "vrtic",
        "naziv": "Vrtic / jaslice",
        "tagovi": [{"amenity": "kindergarten"}, {"amenity": "childcare"}],
        "tezina": 3,
    },
    {
        "id": "skola",
        "naziv": "Skola",
        "tagovi": [{"amenity": "school"}],
        "tezina": 3,
    },
    {
        "id": "bolnica",
        "naziv": "Bolnica",
        "tagovi": [{"amenity": "hospital"}],
        "tezina": 3,
    },
    {
        "id": "dom_za_stare",
        "naziv": "Dom za stare",
        "tagovi": [{"amenity": "nursing_home"}, {"social_facility": "nursing_home"}],
        "tezina": 3,
    },
    {
        "id": "klinika",
        "naziv": "Klinika / dom zdravlja",
        "tagovi": [{"amenity": "clinic"}, {"amenity": "doctors"}],
        "tezina": 2,
    },
    {
        "id": "socijalna",
        "naziv": "Socijalna ustanova",
        "tagovi": [{"amenity": "social_facility"}],
        "tezina": 2,
    },
    {
        "id": "drustveni_centar",
        "naziv": "Drustveni centar",
        "tagovi": [{"amenity": "community_centre"}],
        "tezina": 1,
    },
]