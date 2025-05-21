from typing import Dict, Any, Optional

from pydantic import BaseModel, Field


# Define the data models for requests and responses
class APIResponse(BaseModel):
    """Base model for API responses"""

    success: bool = Field(
        default=False, description="Whether the request was successful"
    )
    error: Optional[str] = Field(default=None, description="Error message if any")


class HumanLoopRequestData(BaseModel):
    """Model for human-in-the-loop request data"""

    task_id: str = Field(description="Task identifier")
    conversation_id: str = Field(description="Conversation identifier")
    request_id: str = Field(description="Request identifier")
    loop_type: str = Field(description="Type of loop")
    context: Dict[str, Any] = Field(
        description="Context information provided to humans"
    )
    platform: str = Field(description="Platform being used, e.g. wechat, feishu")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class HumanLoopStatusParams(BaseModel):
    """Model for getting human-in-the-loop status parameters"""

    conversation_id: str = Field(description="Conversation identifier")
    request_id: str = Field(description="Request identifier")
    platform: str = Field(description="Platform being used")


class HumanLoopStatusResponse(APIResponse):
    """Model for human-in-the-loop status response"""

    status: str = Field(default="pending", description="Request status")
    response: Optional[Any] = Field(default=None, description="Human response data")
    feedback: Optional[Any] = Field(default=None, description="Feedback data")
    responded_by: Optional[str] = Field(
        default=None, description="Responder information"
    )
    responded_at: Optional[str] = Field(default=None, description="Response timestamp")


class HumanLoopCancelData(BaseModel):
    """Model for canceling human-in-the-loop request"""

    conversation_id: str = Field(description="Conversation identifier")
    request_id: str = Field(description="Request identifier")
    platform: str = Field(description="Platform being used")


class HumanLoopCancelConversationData(BaseModel):
    """Model for canceling entire conversation"""

    conversation_id: str = Field(description="Conversation identifier")
    platform: str = Field(description="Platform being used")


class HumanLoopContinueData(BaseModel):
    """Model for continuing human-in-the-loop interaction"""

    conversation_id: str = Field(description="Conversation identifier")
    request_id: str = Field(description="Request identifier")
    task_id: str = Field(description="Task identifier")
    context: Dict[str, Any] = Field(
        description="Context information provided to humans"
    )
    platform: str = Field(description="Platform being used")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
