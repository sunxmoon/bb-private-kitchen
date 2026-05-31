import json
from unittest.mock import AsyncMock, patch

import pytest
from conftest import _login

from app import crud, schemas
from app.ai_client import RECIPE_PROMPT_TEMPLATE
from app.recipe_utils import parse_recipe_from_form as _parse_recipe_from_form

MOCK_RECIPE_JSON = json.dumps({
    "ingredients": [
        {"name": "五花肉", "amount": "500g"},
        {"name": "冰糖", "amount": "30g"},
    ],
    "steps": [
        "五花肉切块，冷水下锅焯水3分钟",
        "锅中放少许油，加入冰糖小火炒出糖色",
        "放入五花肉翻炒上色，加入葱姜八角",
        "加入料酒、生抽、老抽，倒入开水没过肉面",
        "大火烧开后转小火慢炖45分钟",
        "最后大火收汁，出锅装盘",
    ],
    "cook_time": "60分钟",
    "difficulty": "中等",
    "tips": "焯水后用温水冲洗，肉质更嫩",
}, ensure_ascii=False)


@pytest.fixture
def dish(db):
    """Create a dish for testing."""
    dish_data = schemas.DishCreate(
        name="红烧肉",
        description="经典家常菜",
        created_by=1,
    )
    return crud.create_dish(db, dish_data)


@pytest.fixture
def user(db):
    """Create a user for testing."""
    user_data = schemas.UserCreate(name="testuser", password="testpass666")
    return crud.create_user(db, user_data)


class TestRecipeModel:
    def test_create_recipe(self, db, dish, user):
        content = json.loads(MOCK_RECIPE_JSON)
        recipe = crud.create_or_update_recipe(db, dish.id, content, user.id)
        assert recipe.id is not None
        assert recipe.dish_id == dish.id
        assert recipe.generated_by == user.id
        assert recipe.content["cook_time"] == "60分钟"

    def test_get_recipe_by_dish(self, db, dish, user):
        content = json.loads(MOCK_RECIPE_JSON)
        crud.create_or_update_recipe(db, dish.id, content, user.id)
        recipe = crud.get_recipe_by_dish(db, dish.id)
        assert recipe is not None
        assert recipe.dish_id == dish.id

    def test_update_recipe(self, db, dish, user):
        content = json.loads(MOCK_RECIPE_JSON)
        crud.create_or_update_recipe(db, dish.id, content, user.id)

        updated = dict(content)
        updated["cook_time"] = "90分钟"
        recipe = crud.create_or_update_recipe(db, dish.id, updated, user.id)
        assert recipe.content["cook_time"] == "90分钟"

    def test_recipe_dish_relationship(self, db, dish, user):
        content = json.loads(MOCK_RECIPE_JSON)
        crud.create_or_update_recipe(db, dish.id, content, user.id)
        db.refresh(dish)
        assert dish.recipe is not None
        assert dish.recipe.content["difficulty"] == "中等"

    def test_recipe_dish_cascade_delete(self, db, dish, user):
        content = json.loads(MOCK_RECIPE_JSON)
        crud.create_or_update_recipe(db, dish.id, content, user.id)
        db.delete(dish)
        db.commit()
        assert crud.get_recipe_by_dish(db, dish.id) is None


class TestRecipeAPI:
    def test_ai_status_endpoint(self, client):
        resp = client.get("/api/ai-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data

    @patch("app.ai_client.AIClient.check_available", new_callable=AsyncMock)
    @patch("app.ai_client.AIClient.generate_recipe", new_callable=AsyncMock)
    def test_generate_recipe(self, mock_generate, mock_check, client, db, dish):
        """Test generating a recipe via API."""
        mock_check.return_value = True
        mock_generate.return_value = json.loads(MOCK_RECIPE_JSON)
        _login(client, db)
        resp = client.post(f"/generate-recipe/{dish.id}", data={"csrf_token": "test-csrf-token"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    @patch("app.ai_client.AIClient.check_available", new_callable=AsyncMock)
    @patch("app.ai_client.AIClient.generate_recipe", new_callable=AsyncMock)
    def test_generate_recipe_already_exists(self, mock_generate, mock_check, client, db, dish):
        """Test generating recipe when one already exists — should update."""
        mock_check.return_value = True
        _login(client, db)
        mock_generate.return_value = json.loads(MOCK_RECIPE_JSON)
        resp1 = client.post(f"/generate-recipe/{dish.id}", data={"csrf_token": "test-csrf-token"})
        assert resp1.status_code == 200

        mock_generate.return_value = json.loads(MOCK_RECIPE_JSON.replace("60分钟", "45分钟"))
        resp2 = client.post(f"/generate-recipe/{dish.id}", data={"csrf_token": "test-csrf-token"})
        assert resp2.status_code == 200

    def test_recipe_content(self, client, db, dish):
        """Test getting recipe content for a dish."""
        _login(client, db)
        resp = client.get(f"/recipe-content/{dish.id}")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    @patch("app.ai_client.AIClient.check_available", new_callable=AsyncMock)
    def test_generate_recipe_ai_unavailable(self, mock_check, client, db, dish):
        """Test generating recipe when AI is unavailable."""
        mock_check.return_value = False
        _login(client, db)
        resp = client.post(f"/generate-recipe/{dish.id}", data={"csrf_token": "test-csrf-token"})
        assert resp.status_code == 200
        assert "ingredients" not in resp.text


class TestRecipeFormEndpoints:
    @patch("app.ai_client.AIClient.check_available", new_callable=AsyncMock)
    @patch("app.ai_client.AIClient.generate_recipe", new_callable=AsyncMock)
    def test_generate_recipe_form_for_existing_dish(self, mock_generate, mock_check, client, db, dish):
        """Test generating recipe form for an existing dish — returns recipe form HTML."""
        mock_check.return_value = True
        mock_generate.return_value = json.loads(MOCK_RECIPE_JSON)
        _login(client, db)
        resp = client.post(f"/generate-recipe-form/{dish.id}", data={"csrf_token": "test-csrf-token"})
        assert resp.status_code == 200
        assert "60分钟" in resp.text  # cook_time from mock
        # Recipe should be saved to DB
        recipe = crud.get_recipe_by_dish(db, dish.id)
        assert recipe is not None

    @patch("app.ai_client.AIClient.check_available", new_callable=AsyncMock)
    @patch("app.ai_client.AIClient.generate_recipe", new_callable=AsyncMock)
    def test_generate_recipe_form_for_new_dish(self, mock_generate, mock_check, client, db):
        """Test generating recipe form for a new dish (by name+description)."""
        mock_check.return_value = True
        mock_generate.return_value = json.loads(MOCK_RECIPE_JSON)
        _login(client, db)
        resp = client.post(
            "/generate-recipe-form",
            data={
                "name": "测试菜",
                "description": "一道测试菜",
                "csrf_token": "test-csrf-token",
            },
        )
        assert resp.status_code == 200
        assert "60分钟" in resp.text  # cook_time from mock

    @patch("app.ai_client.AIClient.check_available", new_callable=AsyncMock)
    def test_generate_recipe_form_ai_unavailable(self, mock_check, client, db, dish):
        """Test AI unavailable in form."""
        mock_check.return_value = False
        _login(client, db)
        resp = client.post(f"/generate-recipe-form/{dish.id}", data={"csrf_token": "test-csrf-token"})
        assert resp.status_code == 200
        assert "AI不可用" in resp.text

    def test_create_dish_with_recipe(self, client, db):
        """Test creating a dish with recipe form data."""
        _login(client, db)
        resp = client.post(
            "/create-dish",
            data={
                "name": "带菜谱的菜",
                "description": "描述",
                "recipe_ingredients": "500g 五花肉\n30g 冰糖",
                "recipe_steps": "步骤一\n步骤二",
                "recipe_cook_time": "30分钟",
                "recipe_difficulty": "简单",
                "recipe_tips": "小提示",
                "csrf_token": "test-csrf-token",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        dish = crud.get_dishes(db)[-1]
        recipe = crud.get_recipe_by_dish(db, dish.id)
        assert recipe is not None
        assert len(recipe.content["ingredients"]) == 2
        assert recipe.content["cook_time"] == "30分钟"

    def test_update_dish_with_recipe(self, client, db, dish):
        """Test updating a dish with recipe form data."""
        _login(client, db)
        resp = client.post(
            f"/update-dish/{dish.id}",
            data={
                "name": "更新后的菜",
                "description": "新描述",
                "recipe_ingredients": "100g 牛肉",
                "recipe_steps": "新步骤",
                "recipe_cook_time": "20分钟",
                "recipe_difficulty": "困难",
                "csrf_token": "test-csrf-token",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        recipe = crud.get_recipe_by_dish(db, dish.id)
        assert recipe is not None
        assert recipe.content["ingredients"][0]["amount"] == "100g"
        assert recipe.content["difficulty"] == "困难"


class TestParseRecipeForm:
    def test_parse_full(self):
        content = _parse_recipe_from_form(
            "500g 五花肉\n30g 冰糖",
            "切块\n焯水\n翻炒",
            "45分钟", "中等", "小心烫手",
        )
        assert content is not None
        assert len(content["ingredients"]) == 2
        assert content["ingredients"][0] == {"amount": "500g", "name": "五花肉"}
        assert len(content["steps"]) == 3
        assert content["cook_time"] == "45分钟"
        assert content["difficulty"] == "中等"
        assert content["tips"] == ["小心烫手"]

    def test_parse_empty(self):
        assert _parse_recipe_from_form("", "", "", "", "") is None

    def test_parse_whitespace_only(self):
        assert _parse_recipe_from_form("  ", "\n  \n", "", "", "") is None

    def test_parse_malformed_ingredient(self):
        content = _parse_recipe_from_form("五花肉", "", "", "", "")
        assert content is not None
        assert content["ingredients"][0]["amount"] == ""


class TestAIClient:
    def test_prompt_format(self):
        """Test the prompt template renders correctly."""
        prompt = RECIPE_PROMPT_TEMPLATE.format(
            dish_name="麻婆豆腐",
            description_text="菜品描述：麻辣鲜香"
        )
        assert "麻婆豆腐" in prompt
        assert "麻辣鲜香" in prompt
        assert "JSON" in prompt
        assert "ingredients" in prompt
        assert "steps" in prompt
