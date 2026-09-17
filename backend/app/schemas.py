from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    accessToken: str
    tokenType: str = "bearer"


class JDTextRequest(BaseModel):
    rawInput: str


class CreateApplicationRequest(BaseModel):
    jobDescriptionId: str


class UpdateApplicationRequest(BaseModel):
    recipientEmail: str | None = None
    emailSubject: str | None = None
    emailBody: str | None = None
    selectedCvId: str | None = None


class UpdateCoverLetterRequest(BaseModel):
    coverLetter: str


class SendRequest(BaseModel):
    idempotencyKey: str
    simulateFailure: bool = False  # mock-backend-only testing hook, ignored when EMAIL_BACKEND != "mock"
