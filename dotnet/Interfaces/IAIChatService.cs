using dotnet.Dtos.Conversation;
using dotnet.Dtos.Message;
using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace dotnet.Interfaces
{
    public interface IAIChatService
    {
        Task<IEnumerable<ConversationDto>> GetConversationsByPlanId(Guid planId);
        Task<ConversationDto> CreateConversation(CreateConversationDto createDbDto);
        Task<ConversationDto> UpdateConversationTitle(Guid conversationId, UpdateConversationTitleDto updateDto);
        Task<IEnumerable<MessageDto>> GetMessagesByConversationId(Guid conversationId);
        Task<MessageDto> AddMessage(CreateMessageDto createMessageDto);
    }
}
