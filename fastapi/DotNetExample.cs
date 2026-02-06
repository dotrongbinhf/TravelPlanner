using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace DotNetToPythonExample
{
    /// <summary>
    /// Example demonstrating how to call the FastAPI Python service from .NET
    /// </summary>
    public class PythonApiClient
    {
        private readonly HttpClient _httpClient;
        private readonly string _baseUrl;

        public PythonApiClient(string baseUrl = "http://localhost:8000")
        {
            _httpClient = new HttpClient();
            _baseUrl = baseUrl;
        }

        /// <summary>
        /// Test the Python API health endpoint
        /// </summary>
        public async Task<string> CheckHealthAsync()
        {
            try
            {
                var response = await _httpClient.GetAsync($"{_baseUrl}/health");
                response.EnsureSuccessStatusCode();
                return await response.Content.ReadAsStringAsync();
            }
            catch (Exception ex)
            {
                return $"Error: {ex.Message}";
            }
        }

        /// <summary>
        /// Send a test message to the Python echo endpoint
        /// </summary>
        public async Task<string> SendEchoMessageAsync(string message, object data = null)
        {
            try
            {
                var requestBody = new
                {
                    message = message,
                    data = data
                };

                var json = JsonSerializer.Serialize(requestBody);
                var content = new StringContent(json, Encoding.UTF8, "application/json");

                var response = await _httpClient.PostAsync($"{_baseUrl}/api/test/echo", content);
                response.EnsureSuccessStatusCode();
                
                return await response.Content.ReadAsStringAsync();
            }
            catch (Exception ex)
            {
                return $"Error: {ex.Message}";
            }
        }

        /// <summary>
        /// Call a custom Python endpoint for processing
        /// </summary>
        public async Task<string> ProcessDataAsync(string message, bool callDotnet = false)
        {
            try
            {
                var requestBody = new
                {
                    message = message,
                    data = new
                    {
                        call_dotnet = callDotnet,
                        timestamp = DateTime.UtcNow
                    }
                };

                var json = JsonSerializer.Serialize(requestBody);
                var content = new StringContent(json, Encoding.UTF8, "application/json");

                var response = await _httpClient.PostAsync($"{_baseUrl}/api/test/process", content);
                response.EnsureSuccessStatusCode();
                
                return await response.Content.ReadAsStringAsync();
            }
            catch (Exception ex)
            {
                return $"Error: {ex.Message}";
            }
        }
    }

    /// <summary>
    /// Example usage
    /// </summary>
    class Program
    {
        static async Task Main(string[] args)
        {
            var client = new PythonApiClient("http://localhost:8000");

            Console.WriteLine("=== Testing Python API Integration ===\n");

            // Test 1: Health check
            Console.WriteLine("1. Testing health check...");
            var healthResult = await client.CheckHealthAsync();
            Console.WriteLine($"Response: {healthResult}\n");

            // Test 2: Echo message
            Console.WriteLine("2. Testing echo endpoint...");
            var echoResult = await client.SendEchoMessageAsync(
                "Hello from .NET!", 
                new { test = true, source = "CSharp" }
            );
            Console.WriteLine($"Response: {echoResult}\n");

            // Test 3: Process data
            Console.WriteLine("3. Testing process endpoint...");
            var processResult = await client.ProcessDataAsync(
                "Process this travel plan", 
                callDotnet: false
            );
            Console.WriteLine($"Response: {processResult}\n");

            Console.WriteLine("=== All tests completed ===");
        }
    }
}
