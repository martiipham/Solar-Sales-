from pydantic import BaseModel

class VoiceTranscription(BaseModel):
    call_id: str
    text_transcription: str
    audio_url: str
    transcription_time: int
