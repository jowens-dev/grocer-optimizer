from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def test_recipe_estimate_prioritizes_preferred_stores():
    response = client.post(
        "/recipes/estimate",
        json={
            "name": "Breakfast",
            "ingredients": [
                {"name": "milk", "quantity": 1, "unit": "gallon"}
            ],
            "preferred_stores": ["Kroger", "Walmart"],
            "mode": "maximize_savings",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recipe_name"] == "Breakfast"
    assert payload["selected_store"] == "Kroger"
    assert payload["estimated_total"] == 3.29
    assert payload["ingredients"][0]["store"] == "Kroger"
