using System.ComponentModel.DataAnnotations;

namespace dotnet.Dtos.ExternalApi
{
    /// <summary>
    /// Request DTO for Google Flights API via SerpApi.
    /// API Reference: https://serpapi.com/google-flights-api
    /// </summary>
    public class FlightSearchRequestDto
    {
        // === Search Query ===

        /// <summary>
        /// Departure airport code (e.g., "CDG", "SGN") or location kgmid (e.g., "/m/0vzm").
        /// Multiple airports separated by comma (e.g., "CDG,ORY,/m/04jpl").
        /// </summary>
        [Required]
        public string? DepartureId { get; set; }

        /// <summary>
        /// Arrival airport code (e.g., "AUS", "HND") or location kgmid.
        /// Multiple airports separated by comma.
        /// </summary>
        [Required]
        public string? ArrivalId { get; set; }

        // === Advanced Google Flights Parameters ===

        /// <summary>
        /// Flight type. Options: 1 = Round trip (default), 2 = One way, 3 = Multi-city.
        /// When set to 3, use MultiCityJson to set flight information.
        /// To get returning flights for Round trip (1), make another request using DepartureToken.
        /// </summary>
        public int Type { get; set; } = 1;

        /// <summary>
        /// Outbound date. Format: YYYY-MM-DD (e.g., "2026-03-10").
        /// </summary>
        [Required]
        public string? OutboundDate { get; set; }

        /// <summary>
        /// Return date. Format: YYYY-MM-DD (e.g., "2026-03-16").
        /// Required if Type is set to 1 (Round trip).
        /// </summary>
        public string? ReturnDate { get; set; }

        /// <summary>
        /// Travel class. Options: 1 = Economy (default), 2 = Premium economy, 3 = Business, 4 = First.
        /// </summary>
        public int TravelClass { get; set; } = 1;

        /// <summary>
        /// Multi-city flight information as a JSON string. Used when Type = 3.
        /// Each object: { "departure_id": "...", "arrival_id": "...", "date": "...", "times": "..." (optional) }
        /// </summary>
        public string? MultiCityJson { get; set; }

        // === Number of Passengers ===

        /// <summary>
        /// Number of adults. Default: 1.
        /// </summary>
        public int Adults { get; set; } = 1;

        /// <summary>
        /// Number of children. Default: 0.
        /// </summary>
        public int Children { get; set; } = 0;

        /// <summary>
        /// Number of infants in seat. Default: 0.
        /// </summary>
        public int InfantsInSeat { get; set; } = 0;

        /// <summary>
        /// Number of infants on lap. Default: 0.
        /// </summary>
        public int InfantsOnLap { get; set; } = 0;

        // === Localization ===

        /// <summary>
        /// Currency of the returned prices. Default: "USD".
        /// See: https://serpapi.com/google-travel-currencies
        /// </summary>
        public string Currency { get; set; } = "USD";

        /// <summary>
        /// Language. Two-letter code (e.g., "en", "es", "fr").
        /// See: https://serpapi.com/google-languages
        /// </summary>
        public string Hl { get; set; } = "en";

        /// <summary>
        /// Country. Two-letter code (e.g., "us", "uk", "fr").
        /// See: https://serpapi.com/google-countries
        /// </summary>
        public string Gl { get; set; } = "us";

        // === Sorting ===

        /// <summary>
        /// Sorting order of results.
        /// Options: 1 = Top flights (default), 2 = Price, 3 = Departure time, 4 = Arrival time, 5 = Duration, 6 = Emissions.
        /// </summary>
        public int? SortBy { get; set; }

        // === Advanced Filters ===

        /// <summary>
        /// Number of stops. Options: 0 = Any (default), 1 = Nonstop only, 2 = 1 stop or fewer, 3 = 2 stops or fewer.
        /// </summary>
        public int? Stops { get; set; }

        /// <summary>
        /// Airline codes to exclude. Comma-separated 2-character IATA codes (e.g., "UA,AA").
        /// Also supports alliances: STAR_ALLIANCE, SKYTEAM, ONEWORLD.
        /// Cannot be used with IncludeAirlines.
        /// </summary>
        public string? ExcludeAirlines { get; set; }

        /// <summary>
        /// Airline codes to include. Comma-separated 2-character IATA codes (e.g., "UA,AA").
        /// Also supports alliances: STAR_ALLIANCE, SKYTEAM, ONEWORLD.
        /// Cannot be used with ExcludeAirlines.
        /// </summary>
        public string? IncludeAirlines { get; set; }

        /// <summary>
        /// Number of carry-on bags. Default: 0.
        /// Should not exceed total passengers with carry-on bag allowance.
        /// </summary>
        public int? Bags { get; set; }

        /// <summary>
        /// Maximum ticket price. Default: unlimited.
        /// </summary>
        public int? MaxPrice { get; set; }

        /// <summary>
        /// Outbound times range. Two or four comma-separated numbers (hours 0-23).
        /// "4,18" = 4:00 AM - 7:00 PM departure.
        /// "4,18,3,19" = departure 4AM-7PM, arrival 3AM-8PM.
        /// </summary>
        public string? OutboundTimes { get; set; }

        /// <summary>
        /// Return times range. Same format as OutboundTimes.
        /// Only used when Type = 1 (Round trip).
        /// </summary>
        public string? ReturnTimes { get; set; }

        /// <summary>
        /// Emission level filter. Options: 1 = Less emissions only.
        /// </summary>
        public int? Emissions { get; set; }

        /// <summary>
        /// Layover duration range in minutes. Two comma-separated numbers.
        /// Example: "90,330" for 1h30m to 5h30m.
        /// </summary>
        public string? LayoverDuration { get; set; }

        /// <summary>
        /// Connecting airport codes to exclude. Comma-separated (e.g., "CDG,AUS").
        /// </summary>
        public string? ExcludeConns { get; set; }

        /// <summary>
        /// Maximum total flight duration in minutes (e.g., 1500 for 25 hours).
        /// </summary>
        public int? MaxDuration { get; set; }

        // === Next Flights / Booking ===

        /// <summary>
        /// Token for retrieving returning flights (Round trip) or next leg (Multi-city).
        /// Found in the departure flight results. Cannot be used with BookingToken (Removed).
        /// </summary>
        public string? DepartureToken { get; set; }
    }
}
