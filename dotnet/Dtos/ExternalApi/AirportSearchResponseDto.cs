using System.Text.Json.Serialization;

namespace dotnet.Dtos.ExternalApi
{
    /// <summary>
    /// Response DTO for searching airports via SerpApi Google Flights Autocomplete.
    /// API Reference: https://serpapi.com/google-flights-autocomplete-api
    /// </summary>
    public class AirportAutocompleteResponseDto
    {
        /// <summary>List of location suggestions with associated airports</summary>
        public List<AirportSuggestionDto>? Suggestions { get; set; }

        /// <summary>
        /// Error message set by the service when the external API call fails. Not part of API response.
        /// </summary>
        [JsonIgnore]
        public string? Error { get; set; }
    }

    public class AirportSuggestionDto
    {
        /// <summary>Position of the suggestion in the list</summary>
        public int Position { get; set; }

        /// <summary>Name of the suggested location (e.g., "Seoul, South Korea")</summary>
        public string? Name { get; set; }

        /// <summary>Type of the suggested location: "city" or "region"</summary>
        public string? Type { get; set; }

        /// <summary>Description of the suggested location (e.g., "Capital of South Korea")</summary>
        public string? Description { get; set; }

        /// <summary>Google Knowledge Graph ID (kgmid) of the suggested location</summary>
        public string? Id { get; set; }

        /// <summary>List of airports near this location</summary>
        public List<AutocompleteAirportDto>? Airports { get; set; }
    }

    public class AutocompleteAirportDto
    {
        /// <summary>Full name of the airport (e.g., "Incheon International Airport")</summary>
        public string? Name { get; set; }

        /// <summary>Airport IATA code (e.g., "ICN"). Used as departure_id/arrival_id for Flights API.</summary>
        public string? Id { get; set; }

        /// <summary>City where the airport is located (e.g., "Seoul")</summary>
        public string? City { get; set; }

        /// <summary>Google Knowledge Graph ID (kgmid) of the city</summary>
        public string? CityId { get; set; }

        /// <summary>Distance from the city to the airport (e.g., "31 mi")</summary>
        public string? Distance { get; set; }
    }
}
