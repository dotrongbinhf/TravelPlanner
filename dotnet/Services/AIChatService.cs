using dotnet.Data;
using dotnet.Dtos.Conversation;
using dotnet.Dtos.Message;
using dotnet.Entites;
using dotnet.Interfaces;
using Microsoft.EntityFrameworkCore;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace dotnet.Services
{
    public class AIChatService : IAIChatService
    {
        private readonly MySQLDbContext _context;
        private readonly ICurrentUser _currentUser;

        public AIChatService(MySQLDbContext context, ICurrentUser currentUser)
        {
            _context = context;
            _currentUser = currentUser;
        }

        public async Task<IEnumerable<ConversationDto>> GetConversationsByPlanId(Guid planId)
        {
            var userId = _currentUser.Id;
            
            var hasAccess = await _context.Participants.AnyAsync(p => p.PlanId == planId && p.UserId == userId);
            if (!hasAccess) return new List<ConversationDto>();

            var conversations = await _context.Conversations
                .Where(c => c.PlanId == planId)
                .OrderByDescending(c => c.ModifiedAt ?? c.CreatedAt)
                .Select(c => new ConversationDto
                {
                    Id = c.Id,
                    PlanId = c.PlanId,
                    Title = c.Title,
                    CreatedAt = c.CreatedAt,
                    UpdatedAt = c.ModifiedAt
                })
                .ToListAsync();

            return conversations;
        }

        public async Task<ConversationDto> CreateConversation(CreateConversationDto createDto)
        {
            var userId = _currentUser.Id;
            var hasAccess = await _context.Participants.AnyAsync(p => p.PlanId == createDto.PlanId && p.UserId == userId);
            if (!hasAccess) throw new UnauthorizedAccessException("You don't have access to this plan");

            var conversation = new Conversation
            {
                Id = Guid.NewGuid(),
                PlanId = createDto.PlanId,
                Title = string.IsNullOrWhiteSpace(createDto.Title) ? "New Conversation" : createDto.Title,
            };

            await _context.Conversations.AddAsync(conversation);
            await _context.SaveChangesAsync();

            return new ConversationDto
            {
                Id = conversation.Id,
                PlanId = conversation.PlanId,
                Title = conversation.Title,
                CreatedAt = conversation.CreatedAt,
                UpdatedAt = conversation.ModifiedAt
            };
        }

        public async Task<ConversationDto> UpdateConversationTitle(Guid conversationId, UpdateConversationTitleDto updateDto)
        {
            var conversation = await _context.Conversations
                .Include(c => c.Plan)
                .ThenInclude(p => p.Participants)
                .FirstOrDefaultAsync(c => c.Id == conversationId);

            if (conversation == null) throw new KeyNotFoundException("Conversation not found");

            var userId = _currentUser.Id;
            if (!conversation.Plan.Participants.Any(p => p.UserId == userId))
                throw new UnauthorizedAccessException("You don't have access to this conversation");

            conversation.Title = updateDto.Title;
            _context.Conversations.Update(conversation);
            await _context.SaveChangesAsync();

            return new ConversationDto
            {
                Id = conversation.Id,
                PlanId = conversation.PlanId,
                Title = conversation.Title,
                CreatedAt = conversation.CreatedAt,
                UpdatedAt = conversation.ModifiedAt
            };
        }

        public async Task<IEnumerable<MessageDto>> GetMessagesByConversationId(Guid conversationId)
        {
            var userId = _currentUser.Id;
            var conversation = await _context.Conversations
                .Include(c => c.Plan)
                .ThenInclude(p => p.Participants)
                .FirstOrDefaultAsync(c => c.Id == conversationId);

            if (conversation == null) return new List<MessageDto>();
            if (!conversation.Plan.Participants.Any(p => p.UserId == userId))
                throw new UnauthorizedAccessException("You don't have access to this conversation");

            var messages = await _context.Messages
                .Where(m => m.ConversationId == conversationId)
                .OrderBy(m => m.CreatedAt)
                .Select(m => new MessageDto
                {
                    Id = m.Id,
                    ConversationId = m.ConversationId,
                    Content = m.Content,
                    MessageRole = m.MessageRole,
                    CreatedAt = m.CreatedAt,
                    GeneratedPlanData = m.GeneratedPlanData,
                    ApplyGeneratedPlanAt = m.ApplyGeneratedPlanAt
                })
                .ToListAsync();

            return messages;
        }

        public async Task<MessageDto> AddMessage(CreateMessageDto createMessageDto)
        {
            var userId = _currentUser.Id;
            var conversation = await _context.Conversations
                .Include(c => c.Plan)
                .ThenInclude(p => p.Participants)
                .FirstOrDefaultAsync(c => c.Id == createMessageDto.ConversationId);

            if (conversation == null) throw new KeyNotFoundException("Conversation not found");
            if (!conversation.Plan.Participants.Any(p => p.UserId == userId))
                throw new UnauthorizedAccessException("You don't have access to this conversation");

            var message = new Message
            {
                Id = Guid.NewGuid(),
                ConversationId = createMessageDto.ConversationId,
                Content = createMessageDto.Content,
                MessageRole = createMessageDto.MessageRole,
                GeneratedPlanData = createMessageDto.GeneratedPlanData
            };

            conversation.ModifiedAt = DateTimeOffset.UtcNow;
            _context.Conversations.Update(conversation);

            await _context.Messages.AddAsync(message);
            await _context.SaveChangesAsync();

            return new MessageDto
            {
                Id = message.Id,
                ConversationId = message.ConversationId,
                Content = message.Content,
                MessageRole = message.MessageRole,
                CreatedAt = message.CreatedAt,
                GeneratedPlanData = message.GeneratedPlanData,
                ApplyGeneratedPlanAt = message.ApplyGeneratedPlanAt
            };
        }

        public async Task<MessageDto> MarkMessageApplied(Guid messageId)
        {
            var userId = _currentUser.Id;
            var message = await _context.Messages
                .Include(m => m.Conversation)
                .ThenInclude(c => c.Plan)
                .ThenInclude(p => p.Participants)
                .FirstOrDefaultAsync(m => m.Id == messageId);

            if (message == null) throw new KeyNotFoundException("Message not found");
            if (!message.Conversation.Plan.Participants.Any(p => p.UserId == userId))
                throw new UnauthorizedAccessException("You don't have access to this message");

            message.ApplyGeneratedPlanAt = DateTimeOffset.UtcNow;
            _context.Messages.Update(message);
            await _context.SaveChangesAsync();

            return new MessageDto
            {
                Id = message.Id,
                ConversationId = message.ConversationId,
                Content = message.Content,
                MessageRole = message.MessageRole,
                CreatedAt = message.CreatedAt,
                GeneratedPlanData = message.GeneratedPlanData,
                ApplyGeneratedPlanAt = message.ApplyGeneratedPlanAt
            };
        }

        public async Task<bool> DeleteConversation(Guid conversationId)
        {
            var userId = _currentUser.Id;
            var conversation = await _context.Conversations
                .Include(c => c.Plan)
                .FirstOrDefaultAsync(c => c.Id == conversationId);

            if (conversation == null) throw new KeyNotFoundException("Conversation not found");
            if (conversation.Plan.OwnerId != userId)
                throw new UnauthorizedAccessException("You don't have access to this conversation");

            _context.Conversations.Remove(conversation);
            await _context.SaveChangesAsync();

            return true;
        }
    }
}
