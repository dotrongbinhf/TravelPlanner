using System.Text.Json.Serialization;

namespace dotnet.Dtos.ExternalApi
{
    /// <summary>
    /// Response DTO for Google Flights API via SerpApi.
    /// API Reference: https://serpapi.com/google-flights-api
    /// </summary>
    public class FlightSearchResponseDto
    {
        /// <summary>Best flight options curated by Google</summary>
        public List<FlightGroupDto>? BestFlights { get; set; }

        /// <summary>Other available flight options</summary>
        public List<FlightGroupDto>? OtherFlights { get; set; }

        /// <summary>Price insights for the route</summary>
        public FlightPriceInsightsDto? PriceInsights { get; set; }

        /// <summary>Airport and city information for departure and arrival</summary>
        public List<FlightAirportInfoDto>? Airports { get; set; }

        /// <summary>
        /// Error message set by the service when the external API call fails. Not part of SerpApi response.
        /// </summary>
        [JsonIgnore]
        public string? Error { get; set; }
    }

    // ========================
    // Flight Group (a complete journey option)
    // ========================

    public class FlightGroupDto
    {
        /// <summary>Individual flight segments in this journey</summary>
        public List<FlightSegmentDto>? Flights { get; set; }

        /// <summary>Layover information between segments</summary>
        public List<FlightLayoverDto>? Layovers { get; set; }

        /// <summary>Total duration of all flights and layovers in minutes</summary>
        public int TotalDuration { get; set; }

        /// <summary>Carbon emissions information</summary>
        public FlightCarbonEmissionsDto? CarbonEmissions { get; set; }

        /// <summary>Ticket price in the selected currency (default: USD)</summary>
        public int Price { get; set; }

        /// <summary>Flight type (e.g., "Round trip", "One way")</summary>
        public string? Type { get; set; }

        /// <summary>URL to the airline logo (or mixed airlines logo)</summary>
        public string? AirlineLogo { get; set; }

        /// <summary>Features of the entire flight (e.g., "Checked baggage for a fee")</summary>
        public List<string>? Extensions { get; set; }

        /// <summary>Token for retrieving returning flights (Round trip) or next leg (Multi-city)</summary>
        public string? DepartureToken { get; set; }
    }

    // ========================
    // Flight Segment (individual flight leg)
    // ========================

    public class FlightSegmentDto
    {
        /// <summary>Departure airport information</summary>
        public FlightAirportDto? DepartureAirport { get; set; }

        /// <summary>Arrival airport information</summary>
        public FlightAirportDto? ArrivalAirport { get; set; }

        /// <summary>Flight duration in minutes</summary>
        public int Duration { get; set; }

        /// <summary>Aircraft type (e.g., "Airbus A320", "Boeing 787")</summary>
        public string? Airplane { get; set; }

        /// <summary>Airline name (e.g., "British Airways", "American")</summary>
        public string? Airline { get; set; }

        /// <summary>URL to the airline's logo</summary>
        public string? AirlineLogo { get; set; }

        /// <summary>Travel class (e.g., "Economy", "Business", "First")</summary>
        public string? TravelClass { get; set; }

        /// <summary>Flight number (e.g., "BA 303", "AA 63")</summary>
        public string? FlightNumber { get; set; }

        /// <summary>Other airlines that also sell this ticket</summary>
        public List<string>? TicketAlsoSoldBy { get; set; }

        /// <summary>Available legroom including unit (e.g., "31 in")</summary>
        public string? Legroom { get; set; }

        /// <summary>Flight features (e.g., "Wi-Fi for a fee", "In-seat power & USB outlets")</summary>
        public List<string>? Extensions { get; set; }

        /// <summary>True if the flight is overnight</summary>
        public bool? Overnight { get; set; }

        /// <summary>True if the flight is often delayed by 30+ minutes</summary>
        public bool? OftenDelayedByOver30Min { get; set; }

        /// <summary>Operating airline that provides the plane and crew (if different from marketing airline)</summary>
        public string? PlaneAndCrewBy { get; set; }
    }

    // ========================
    // Flight Airport
    // ========================

    public class FlightAirportDto
    {
        /// <summary>Airport name (e.g., "Paris Charles de Gaulle Airport")</summary>
        public string? Name { get; set; }

        /// <summary>Airport IATA code (e.g., "CDG", "AUS")</summary>
        public string? Id { get; set; }

        /// <summary>Departure/arrival time (e.g., "2026-03-03 11:55")</summary>
        public string? Time { get; set; }
    }

    // ========================
    // Layover
    // ========================

    public class FlightLayoverDto
    {
        /// <summary>Layover duration in minutes</summary>
        public int Duration { get; set; }

        /// <summary>Airport name for the layover</summary>
        public string? Name { get; set; }

        /// <summary>Airport IATA code for the layover</summary>
        public string? Id { get; set; }

        /// <summary>True if the layover is overnight</summary>
        public bool? Overnight { get; set; }
    }

    // ========================
    // Carbon Emissions
    // ========================

    public class FlightCarbonEmissionsDto
    {
        /// <summary>Carbon emissions of this flight in grams</summary>
        public int? ThisFlight { get; set; }

        /// <summary>Typical carbon emissions for this route in grams</summary>
        public int? TypicalForThisRoute { get; set; }

        /// <summary>Difference between this flight and typical value in percent</summary>
        public int? DifferencePercent { get; set; }
    }

    // ========================
    // Price Insights
    // ========================

    public class FlightPriceInsightsDto
    {
        /// <summary>Lowest price among returned flights</summary>
        public int? LowestPrice { get; set; }

        /// <summary>Price level of the lowest price (e.g., "low", "typical", "high")</summary>
        public string? PriceLevel { get; set; }

        /// <summary>Typical price range [low, high] for this route</summary>
        public List<int>? TypicalPriceRange { get; set; }

        /// <summary>Price history as array of [timestamp, price] pairs</summary>
        public List<List<long>>? PriceHistory { get; set; }
    }

    // ========================
    // Airport Info (departure/arrival city info)
    // ========================

    public class FlightAirportInfoDto
    {
        /// <summary>Departure airport(s) information</summary>
        public List<FlightCityAirportDto>? Departure { get; set; }

        /// <summary>Arrival airport(s) information</summary>
        public List<FlightCityAirportDto>? Arrival { get; set; }
    }

    public class FlightCityAirportDto
    {
        /// <summary>Airport name and code</summary>
        public FlightAirportCodeDto? Airport { get; set; }

        /// <summary>City name</summary>
        public string? City { get; set; }

        /// <summary>Country name</summary>
        public string? Country { get; set; }

        /// <summary>Country code (e.g., "US", "FR")</summary>
        public string? CountryCode { get; set; }

        /// <summary>URL to the city image</summary>
        public string? Image { get; set; }

        /// <summary>URL to the city thumbnail</summary>
        public string? Thumbnail { get; set; }
    }

    public class FlightAirportCodeDto
    {
        /// <summary>Airport name</summary>
        public string? Name { get; set; }

        /// <summary>Airport IATA code</summary>
        public string? Id { get; set; }
    }
}
