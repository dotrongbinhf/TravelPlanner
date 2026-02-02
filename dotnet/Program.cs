using dotnet.Data;
using dotnet.Helpers;
using dotnet.Interfaces;
using dotnet.Services;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using System.Security.Claims;
using System.Text;

var builder = WebApplication.CreateBuilder(args);

// Add Configurations
builder.Services.Configure<CloudinarySettings>(builder.Configuration.GetSection("CloudinarySettings"));

// Add services to the container.
builder.Services.AddHttpContextAccessor();
builder.Services.AddScoped<ICurrentUser, CurrentUser>();
builder.Services.AddScoped<ICookieService, CookieService>();
builder.Services.AddSingleton<MongoDbService>();
builder.Services.AddScoped<ICloudinaryService, CloudinaryService>();

builder.Services.AddControllers()
    .AddJsonOptions(options =>
    {
        options.JsonSerializerOptions.Converters.Add(new TimeOnlyJsonConverter());
    });
// Learn more about configuring Swagger/OpenAPI at https://aka.ms/aspnetcore/swashbuckle
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// Connect to Mysql
builder.Services.AddDbContext<MySQLDbContext>(options =>
    options.UseMySql(
        builder.Configuration.GetConnectionString("MySQL"),
        ServerVersion.AutoDetect(builder.Configuration.GetConnectionString("MySQL"))
    )
);

// Connect to PostgreSQL
//builder.Services.AddDbContext<PostgreSQLDbContext>(options =>
//    options.UseNpgsql(
//        builder.Configuration.GetConnectionString("PostgreSQL")
//    )
//);

// JWT
var jwtSection = builder.Configuration.GetSection("Jwt");

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new Microsoft.IdentityModel.Tokens.TokenValidationParameters
        {
            ValidateIssuer = false,
            ValidateAudience = false,
            ValidateLifetime = true,
            ValidateIssuerSigningKey = true,
            //ValidIssuer = jwtSection["Issuer"],
            //ValidAudience = jwtSection["Audience"],
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtSection["AccessTokenSecret"])),
            ClockSkew = TimeSpan.Zero
        };
    });

builder.Services.AddAuthorization();

// Add Cors
builder.Services.AddCors(options =>
{
    options.AddPolicy(name: "CorsAllowEverything", policy =>
    {
        policy
            .WithOrigins("https://localhost:3000")
            .AllowAnyHeader()
            .AllowAnyMethod()
            .AllowCredentials();
    });
});

var app = builder.Build();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseCors("CorsAllowEverything");

app.UseHttpsRedirection();

app.UseAuthorization();

app.MapControllers();

app.Run();
