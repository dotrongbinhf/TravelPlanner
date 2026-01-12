using dotnet.Domains;
using Microsoft.EntityFrameworkCore;

namespace dotnet.Data
{
    public class MySQLDbContext : DbContext
    {
        public MySQLDbContext(DbContextOptions<MySQLDbContext> options) : base(options)
        {
        }

        // Thêm key bởi khi không sử dụng Id gốc ở Entity, EF Core không tự động nhận diện được
        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            //modelBuilder.Entity<CourseNotification>()
            //    .HasKey(cn => new { cn.CourseId, cn.NotificationId });

            //modelBuilder.Entity<Course>()
            //    .HasIndex(c => new { c.InstructorId, c.Title })
            //    .IsUnique();

            base.OnModelCreating(modelBuilder);
        }

        public DbSet<SetUp> SetUps { get; set; }
    }
}
