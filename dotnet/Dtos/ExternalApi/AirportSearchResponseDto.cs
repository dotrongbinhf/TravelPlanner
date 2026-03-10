using System.Text.Json.Serialization;

namespace dotnet.Dtos.ExternalApi
{
    /// <summary>
    /// Response DTO for searching airports by location via AeroDataBox (RapidAPI).
    /// API Reference: https://rapidapi.com/aedbx-aedbx/api/aerodatabox
    /// </summary>
    public class AirportSearchResponseDto
    {
        /// <summary>List of airports found near the specified location</summary>
        public List<AirportDto>? Items { get; set; }

        /// <summary>
        /// Error message set by the service when the external API call fails. Not part of API response.
        /// </summary>
        [JsonIgnore]
        public string? Error { get; set; }
    }

    public class AirportDto
    {
        /// <summary>ICAO code of the airport (e.g., "KJFK")</summary>
        public string? Icao { get; set; }

        /// <summary>IATA code of the airport (e.g., "JFK"). Used as departure_id/arrival_id for Flights API.</summary>
        public string? Iata { get; set; }

        /// <summary>Full name of the airport (e.g., "John F. Kennedy International Airport")</summary>
        public string? Name { get; set; }

        /// <summary>Short name of the airport (e.g., "Kennedy")</summary>
        public string? ShortName { get; set; }

        /// <summary>Municipality/city name (e.g., "New York")</summary>
        public string? MunicipalityName { get; set; }

        /// <summary>Geographic location of the airport</summary>
        public AirportLocationDto? Location { get; set; }

        /// <summary>Country code (e.g., "US", "VN")</summary>
        public string? CountryCode { get; set; }

        /// <summary>Timezone of the airport (e.g., "America/New_York")</summary>
        public string? TimeZone { get; set; }
    }

    public class AirportLocationDto
    {
        /// <summary>Latitude of the airport</summary>
        public double Lat { get; set; }

        /// <summary>Longitude of the airport</summary>
        public double Lon { get; set; }
    }
}
