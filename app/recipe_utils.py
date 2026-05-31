from . import crud


def parse_recipe_from_form(
    recipe_ingredients: str | None,
    recipe_steps: str | None,
    recipe_cook_time: str | None,
    recipe_difficulty: str | None,
    recipe_tips: str | None,
) -> dict | None:
    ingredients = []
    if recipe_ingredients:
        for line in recipe_ingredients.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                ingredients.append({"amount": parts[0], "name": parts[1]})
            else:
                ingredients.append({"amount": "", "name": parts[0]})
    steps = [s.strip() for s in recipe_steps.strip().split("\n") if s.strip()] if recipe_steps else []
    if not ingredients and not steps:
        return None

    tips = []
    if recipe_tips:
        tips = [t.strip() for t in recipe_tips.strip().split("\n") if t.strip()]

    return {
        "ingredients": ingredients,
        "steps": steps,
        "cook_time": recipe_cook_time.strip() if recipe_cook_time else "",
        "difficulty": recipe_difficulty.strip() if recipe_difficulty else "",
        "tips": tips if tips else [],
    }


def save_recipe_form(db, dish_id, recipe_ingredients, recipe_steps, recipe_cook_time, recipe_difficulty, recipe_tips, user_id):
    content = parse_recipe_from_form(
        recipe_ingredients, recipe_steps, recipe_cook_time, recipe_difficulty, recipe_tips,
    )
    if content:
        crud.create_or_update_recipe(db, dish_id, content, user_id)
