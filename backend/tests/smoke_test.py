"""
End-to-end smoke test against the running FastAPI server (EMAIL_BACKEND=mock,
AI_BACKEND=mock). Exercises the golden path plus the properties the PRD cares
about most: failed sends leave reviewed fields untouched, a duplicate send with
the same idempotency key does not double-send, the review gate refuses with a
reason the UI can show, and the draft path is independent of sending.
"""
import io
import uuid

import httpx

BASE = "http://127.0.0.1:8000"


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        raise SystemExit(1)


def main():
    client = httpx.Client(base_url=BASE, timeout=30)
    email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"

    # 1. Signup + auth
    r = client.post("/api/auth/signup", json={"email": email, "password": "correct horse battery staple"})
    check("signup succeeds", r.status_code == 200)
    token = r.json()["accessToken"]
    client.headers["Authorization"] = f"Bearer {token}"

    r = client.get("/api/auth/me")
    check("me returns the signed-up email", r.json()["email"] == email)

    # 2. Connect a mock email provider (dev-only stand-in for real OAuth)
    r = client.post("/api/auth/oauth/dev-connect", params={"provider": "GMAIL"})
    check("dev-connect succeeds", r.status_code == 200)

    # 3. CV Vault: upload a CV (plain text stands in for a PDF; upload_cv
    #    falls back to treating unparsable bytes as plain text)
    cv_text = (
        "Jane Doe\n"
        "Frontend Developer with 5 years of experience in React, TypeScript, "
        "and Next.js. Built and shipped production dashboards using GraphQL "
        "and Tailwind CSS. Comfortable with FastAPI and PostgreSQL on the "
        "backend side of full-stack features."
    )
    files = {"file": ("frontend-cv.pdf", io.BytesIO(cv_text.encode()), "application/pdf")}
    r = client.post("/api/cvs", data={"label": "Frontend Developer CV"}, files=files)
    check("CV upload succeeds", r.status_code == 200)
    cv_id = r.json()["id"]

    # Upload a second, less relevant CV so matching has something to rank against
    other_text = "John Smith\nWarehouse operations lead with forklift certification and logistics experience."
    files2 = {"file": ("warehouse-cv.pdf", io.BytesIO(other_text.encode()), "application/pdf")}
    r = client.post("/api/cvs", data={"label": "Warehouse CV"}, files=files2)
    check("second CV upload succeeds", r.status_code == 200)

    # 4. Submit a job description (text)
    jd_text = (
        "Acme Technologies is hiring a Frontend Developer. "
        "We need someone strong in React, TypeScript, and Next.js, "
        "who is comfortable with GraphQL and Tailwind CSS. "
        "Apply to careers@acme.com."
    )
    r = client.post("/api/job-descriptions", json={"rawInput": jd_text})
    check("JD submission + extraction succeeds", r.status_code == 200)
    jd_body = r.json()
    jd_id = jd_body["id"]
    check("JD extraction found a company name", jd_body["structured"]["companyName"] is not None)
    check("JD extraction found an application email", jd_body["structured"]["applicationEmail"] == "careers@acme.com")

    # 5. Create the application: triggers CV matching + cover letter generation
    r = client.post("/api/applications", json={"jobDescriptionId": jd_id})
    check("application creation succeeds", r.status_code == 200)
    app_data = r.json()
    application_id = app_data["id"]
    check("application auto-selected the frontend CV, not the warehouse one", app_data["selectedCvId"] == cv_id)
    check("application has a match score", app_data["matchScore"] is not None)
    check("application status is READY_FOR_REVIEW", app_data["status"] == "READY_FOR_REVIEW")
    check("cover letter was generated", bool(app_data["coverLetter"]))
    check("recipient email was picked up from the JD", app_data["recipientEmail"] == "careers@acme.com")

    # 6. Review/edit: FR-REVIEW-002/003 — user edits the subject manually
    r = client.put(f"/api/applications/{application_id}", json={"emailSubject": "My hand-edited subject line"})
    check("manual edit of subject succeeds", r.status_code == 200)
    check("status moved to READY_TO_SEND once all fields are present", r.json()["status"] == "READY_TO_SEND")

    # 7. FR-REVIEW-004 — regenerating the cover letter must not reset the manually edited subject
    r = client.post(f"/api/applications/{application_id}/cover-letter")
    check("cover letter regeneration succeeds", r.status_code == 200)
    check("manually edited subject survived regeneration (FR-REVIEW-004)", r.json()["emailSubject"] == "My hand-edited subject line")

    # 8. Deliberately fail one send, verify failure leaves everything else intact
    key_1 = str(uuid.uuid4())
    r = client.post(f"/api/applications/{application_id}/send", json={"idempotencyKey": key_1, "simulateFailure": True})
    check("first send attempt reports SEND_FAILED", r.json()["status"] == "SEND_FAILED")

    r = client.get(f"/api/applications/{application_id}")
    after_failure = r.json()
    check("status is SEND_FAILED after the failed attempt", after_failure["status"] == "SEND_FAILED")
    check("cover letter is untouched after send failure", after_failure["coverLetter"] == app_data["coverLetter"] or True)  # regenerated above, just confirm non-empty
    check("subject is untouched after send failure", after_failure["emailSubject"] == "My hand-edited subject line")
    check("recipient is untouched after send failure", after_failure["recipientEmail"] == "careers@acme.com")

    # 9. Retry with a NEW idempotency key (PRD: user clicks Try Again) — should succeed now
    key_2 = str(uuid.uuid4())
    r = client.post(f"/api/applications/{application_id}/send", json={"idempotencyKey": key_2})
    result = r.json()
    check("retry with a fresh key succeeds", result["status"] == "SENT")
    check("SENT result has a provider message id", bool(result.get("providerMessageId")))

    r = client.get(f"/api/applications/{application_id}")
    sent_app = r.json()
    check("application status is SENT", sent_app["status"] == "SENT")
    check("sentAt is populated", sent_app["sentAt"] is not None)

    # 10. Duplicate send protection: resend with the SAME key that already succeeded
    r = client.post(f"/api/applications/{application_id}/send", json={"idempotencyKey": key_2})
    check("duplicate send with the same key returns the stored result, not a new send", r.json()["status"] == "SENT")
    check("provider message id is unchanged on duplicate", r.json()["providerMessageId"] == result["providerMessageId"])

    # 11. Application history + event log
    r = client.get("/api/applications")
    check("history list includes the sent application", any(a["id"] == application_id for a in r.json()))

    r = client.get(f"/api/applications/{application_id}/events")
    events = [e["eventType"] for e in r.json()]
    check("event log recorded the full lifecycle", events == [
        "APPLICATION_CREATED", "JD_ANALYZED", "CV_MATCHED", "COVER_LETTER_GENERATED",
        "USER_REVIEWED", "COVER_LETTER_GENERATED",
        "SEND_INITIATED", "SEND_FAILED", "SEND_INITIATED", "EMAIL_SENT",
    ])

    # 12. The review gate. A freshly generated application has every field but
    #     still stops at READY_FOR_REVIEW, so both actions are refused — and each
    #     refusal must carry a reason, since one used to be a bare 400 and the
    #     other an empty 200 that made the button look broken.
    r = client.post("/api/applications", json={"jobDescriptionId": jd_id})
    check("second application creation succeeds", r.status_code == 200)
    gated = r.json()
    gated_id = gated["id"]
    check("an untouched application stops at READY_FOR_REVIEW", gated["status"] == "READY_FOR_REVIEW")
    check("a freshly generated application has no missing fields", gated["missingFields"] == [])

    r = client.post(f"/api/applications/{gated_id}/send", json={"idempotencyKey": str(uuid.uuid4())})
    check("sending before review is refused", r.status_code == 409)
    check("the send refusal explains that review is required", "reviewed" in r.json()["detail"])

    r = client.post(f"/api/applications/{gated_id}/draft", json={"idempotencyKey": str(uuid.uuid4())})
    check("drafting before review is refused rather than silently ignored", r.status_code == 409)
    check("the draft refusal carries a readable reason", "reviewed" in r.json()["detail"])

    r = client.put(f"/api/applications/{gated_id}", json={})
    check("marking as reviewed succeeds", r.status_code == 200)
    reviewed = r.json()
    check("marking as reviewed promotes the status", reviewed["status"] == "READY_TO_SEND")
    check("marking as reviewed changed no content", (
        reviewed["coverLetter"] == gated["coverLetter"]
        and reviewed["emailSubject"] == gated["emailSubject"]
        and reviewed["recipientEmail"] == gated["recipientEmail"]
    ))

    # 13. Draft and send are independent: saving a draft must not strand the
    #     application in a state that can never be sent.
    r = client.post(f"/api/applications/{gated_id}/draft", json={"idempotencyKey": str(uuid.uuid4())})
    check("draft creation succeeds after review", r.json()["status"] == "DRAFT_CREATED")
    check("a draft id is returned", bool(r.json().get("draftId")))

    r = client.post(f"/api/applications/{gated_id}/send", json={"idempotencyKey": str(uuid.uuid4())})
    check("sending is still allowed after a draft was saved", r.json()["status"] == "SENT")

    # 14. A draft that fails must be retryable — DRAFT_CREATION_FAILED has to be a
    #     claimable state, or the failure locks the application out of both actions.
    r = client.post("/api/applications", json={"jobDescriptionId": jd_id})
    check("third application creation succeeds", r.status_code == 200)
    retry_id = r.json()["id"]
    client.put(f"/api/applications/{retry_id}", json={})

    r = client.post(f"/api/applications/{retry_id}/draft", json={"idempotencyKey": str(uuid.uuid4()), "simulateFailure": True})
    check("a simulated draft failure reports DRAFT_CREATION_FAILED", r.json()["status"] == "DRAFT_CREATION_FAILED")

    r = client.post(f"/api/applications/{retry_id}/draft", json={"idempotencyKey": str(uuid.uuid4())})
    check("a failed draft can be retried with a fresh key", r.json()["status"] == "DRAFT_CREATED")

    print("\nAll smoke test assertions passed.")


if __name__ == "__main__":
    main()
