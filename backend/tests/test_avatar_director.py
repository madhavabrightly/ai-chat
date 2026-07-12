from backend.services.avatar_director import (
    create_avatar_action_plan,
    create_model_avatar_action_plan,
)


def test_instant_plan_uses_supported_motion_schema():
    plan = create_avatar_action_plan(
        "I am proud of what we achieved.",
        [{"category": "Career", "emotion": "Joyful"}],
    )

    assert plan["mood"] == "proud"
    assert plan["movement"] == "stand_tall"
    assert plan["director"] == "instant_rules"


def test_model_plan_accepts_only_valid_enum_fields(monkeypatch):
    from backend.models import avatar_action_loader

    monkeypatch.setattr(avatar_action_loader, "avatar_action_model_ready", lambda: True)
    monkeypatch.setattr(
        avatar_action_loader,
        "generate_avatar_action_json",
        lambda messages: (
            '{"mood":"happy","expression":"bright_smile",'
            '"gesture":"hands_open","movement":"gentle_bounce",'
            '"mouth_style":"excited","camera":"medium",'
            '"bone_override":"delete_everything"}'
        ),
    )

    plan = create_model_avatar_action_plan("That is wonderful!", [])

    assert plan["director"] == "modelscope_qwen3_0_6b"
    assert plan["mood"] == "happy"
    assert plan["movement"] == "gentle_bounce"
    assert "bone_override" not in plan


def test_incomplete_model_output_keeps_instant_plan(monkeypatch):
    from backend.models import avatar_action_loader

    monkeypatch.setattr(avatar_action_loader, "avatar_action_model_ready", lambda: True)
    monkeypatch.setattr(
        avatar_action_loader,
        "generate_avatar_action_json",
        lambda messages: '{"mood":"happy"}',
    )

    plan = create_model_avatar_action_plan("A thoughtful answer.", [])

    assert plan["director"] == "instant_rules"
    assert plan["director_ready"] is True
