using System.ComponentModel.DataAnnotations;

namespace dotnet.Dtos.ExternalApi
{
    /// <summary>
    /// Request DTO for searching airports by location via AeroDataBox (RapidAPI).
    /// API Reference: https://rapidapi.com/aedbx-aedbx/api/aerodatabox
    /// Endpoint: GET /airports/search/location
    /// </summary>
    public class AirportSearchByLocationRequestDto
    {
        /// <summary>
        /// Latitude of the search center point. Decimal (-90; 90).
        /// </summary>
        [Required]
        public double Lat { get; set; }

        /// <summary>
        /// Longitude of the search center point. Decimal (-180; 180).
        /// </summary>
        [Required]
        public double Lon { get; set; }

        /// <summary>
        /// Search radius in kilometers. Default: 50.
        /// </summary>
        public int RadiusKm { get; set; } = 50;

        /// <summary>
        /// Maximum number of results to return. Default: 10.
        /// </summary>
        public int Limit { get; set; } = 10;

        /// <summary>
        /// If true, only return airports with flight information. Default: true.
        /// Set to false to include smaller airports without scheduled flights.
        /// </summary>
        public bool WithFlightInfoOnly { get; set; } = true;
    }
}
