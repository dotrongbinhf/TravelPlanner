using System.ComponentModel.DataAnnotations;

namespace dotnet.Dtos.ExternalApi
{
    /// <summary>
    /// Request DTO for searching airports by location name via SerpApi Google Flights Autocomplete.
    /// API Reference: https://serpapi.com/google-flights-autocomplete-api
    /// Endpoint: GET /search?engine=google_flights_autocomplete
    /// </summary>
    public class AirportAutocompleteRequestDto
    {
        /// <summary>
        /// Search query — a location name (e.g., "Bắc Ninh", "Da Nang", "Tokyo").
        /// </summary>
        [Required]
        public string Q { get; set; } = string.Empty;

        /// <summary>
        /// Language for the search results (e.g., "en", "vi", "ja"). Default: "en".
        /// </summary>
        public string Hl { get; set; } = "en";

        /// <summary>
        /// Country code for the search (e.g., "us", "vn", "jp"). Default: "us".
        /// </summary>
        public string Gl { get; set; } = "us";
    }
}
