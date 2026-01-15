using dotnet.Domains;
using Microsoft.EntityFrameworkCore;

namespace dotnet.Data
{
    public class PostgreSQLDbContext : DbContext
    {
        public PostgreSQLDbContext(DbContextOptions<PostgreSQLDbContext> options) : base(options)
        {
        }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            //modelBuilder.Entity<CourseNotification>()
            //    .HasKey(cn => new { cn.CourseId, cn.NotificationId });

            //modelBuilder.Entity<Course>()
            //    .HasIndex(c => new { c.InstructorId, c.Title })
            //    .IsUnique();

            base.OnModelCreating(modelBuilder);
        }
        public DbSet<User> Users { get; set; }
    }
}
