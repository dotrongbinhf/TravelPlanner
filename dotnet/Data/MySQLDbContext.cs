using dotnet.Entites;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using System.Security.Claims;

namespace dotnet.Data
{
    public class MySQLDbContext : DbContext
    {
        private readonly IHttpContextAccessor httpContextAccessor;
        public MySQLDbContext(DbContextOptions<MySQLDbContext> options, IHttpContextAccessor httpContextAccessor) : base(options)
        {
            this.httpContextAccessor = httpContextAccessor;
        }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            //modelBuilder.Entity<Participant>()
            //    .HasKey(pa => new { pa.UserId, pa.PlanId });

            //modelBuilder.Entity<Participant>()
            //    .HasIndex(pa => new { pa.UserId, pa.PlanId })
            //    .IsUnique();

            base.OnModelCreating(modelBuilder);
        }
        public DbSet<User> Users { get; set; }
        public DbSet<Plan> Plans { get; set; }
        public DbSet<Participant> Participants { get; set; }
        public DbSet<ItineraryItem> ItineraryItems { get; set; }
        public DbSet<ExpenseItem> ExpenseItems { get; set; }
        public DbSet<PackingList> PackingLists { get; set; }
        public DbSet<PackingItem> PackingItems { get; set; }
        public DbSet<Note> Notes { get; set; }
        public DbSet<ItineraryDay> ItineraryDays { get; set; }

        public override int SaveChanges()
        {
            ApplyAuditInfo();
            return base.SaveChanges();
        }

        public override Task<int> SaveChangesAsync(
            CancellationToken cancellationToken = default)
        {
            ApplyAuditInfo();
            return base.SaveChangesAsync(cancellationToken);
        }

        private void ApplyAuditInfo()
        {
            var now = DateTime.UtcNow;
            var userId = httpContextAccessor.HttpContext.User.FindFirst(ClaimTypes.NameIdentifier)?.Value;

            foreach (var entry in ChangeTracker.Entries<BaseAuditableEntity>())
            {
                if (entry.State == EntityState.Added)
                {
                    entry.Entity.CreatedAt = now;
                    entry.Entity.CreatedBy = userId;
                }

                if (entry.State == EntityState.Modified)
                {
                    entry.Entity.ModifiedAt = now;
                    entry.Entity.ModifiedBy = userId;
                }
            }
        }
    }
}
