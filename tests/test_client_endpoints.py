"""
Unit and Integration Tests for Client-Facing Web Kiosk Endpoints.

Tests:
- POST /api/v1/session
- GET  /api/v1/session/{session_id}
- POST /api/v1/interact (including enterprise & GIA subsidy detection)
- GET  /api/v1/recommendations/{session_id}
- POST /api/v1/advisor/chat
- DELETE /api/v1/session/{session_id}
"""

import pytest
from httpx import AsyncClient, ASGITransport
from api.server import app


@pytest.mark.asyncio
async def test_client_session_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Session
        resp = await client.post(
            "/api/v1/session",
            json={"language": "Bhojpuri", "phone_number": "+919876543210"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["language"] == "Bhojpuri"
        assert "प्रणाम" in data["initial_prompt_indic"]
        session_id = data["session_id"]

        # 2. Get Active Session
        get_resp = await client.get(f"/api/v1/session/{session_id}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["id"] == session_id
        assert get_data["language"] == "Bhojpuri"

        # 3. Delete Session
        del_resp = await client.delete(f"/api/v1/session/{session_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_client_interact_and_enterprise_scoping():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Start session
        sess_resp = await client.post(
            "/api/v1/session",
            json={"language": "Hindi", "phone_number": "+919876543210"}
        )
        session_id = sess_resp.json()["session_id"]

        # Step 1: Consent
        step1 = await client.post(
            "/api/v1/interact",
            json={"session_id": session_id, "user_transcript": "हाँ, मैं सहमत हूँ और बात करना चाहता हूँ"}
        )
        assert step1.status_code == 200
        assert step1.json()["current_state"] in ("GEOGRAPHIC_INTAKE", "INIT_CONSENT")

        # Step 2: Location
        step2 = await client.post(
            "/api/v1/interact",
            json={"session_id": session_id, "user_transcript": "हम वाराणसी जिले से बानी"}
        )
        assert step2.status_code == 200

        # Step 3: Enterprise tailoring utterance in Bhojpuri
        step3 = await client.post(
            "/api/v1/interact",
            json={
                "session_id": session_id,
                "user_transcript": "हमार नाम राम लखन बा, हम सिलाई मशीन के दुकान खोलल चाहत बानी, 40000 के पूंजी चाही"
            }
        )
        assert step3.status_code == 200
        data3 = step3.json()
        # Verify enterprise and GIA capital subsidy eligibility
        assert data3["eligible_for_gia_asset_grant"] is True
        assert data3["max_capital_subsidy_inr"] == 50000.0


@pytest.mark.asyncio
async def test_client_recommendations_and_advisor():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create session
        sess_resp = await client.post("/api/v1/session", json={"language": "Hindi"})
        session_id = sess_resp.json()["session_id"]

        # Fetch recommendations
        recs_resp = await client.get(f"/api/v1/recommendations/{session_id}")
        assert recs_resp.status_code == 200
        recs = recs_resp.json()
        assert len(recs) >= 3
        # Must have training and government scheme cards
        types = [r["type"] for r in recs]
        assert "Training" in types
        assert "Government support" in types

        # Advisor chat: Subsidy question
        adv_resp = await client.post(
            "/api/v1/advisor/chat",
            json={
                "session_id": session_id,
                "message": "मुझे ₹50,000 की सब्सिडी कैसे मिलेगी?",
                "language": "Hindi"
            }
        )
        assert adv_resp.status_code == 200
        adv_data = adv_resp.json()
        assert "50,000" in adv_data["reply"] or "अनुदान" in adv_data["reply"]
        assert len(adv_data["suggestions"]) > 0
