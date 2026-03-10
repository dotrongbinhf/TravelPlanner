namespace dotnet.Dtos.ExternalApi
{
    /// <summary>
    /// Request DTO for OpenWeatherMap Daily Forecast 16 Days API (2.5).
    /// API Reference: https://openweathermap.org/forecast16
    /// Endpoint: GET /data/2.5/forecast/daily
    /// </summary>
    public class WeatherRequestDto
    {
        /// <summary>
        /// City name, state code (US only) and country code separated by comma.
        /// Use ISO 3166 country codes. Examples: "London", "London,GB", "London,OH,US".
        /// Either Q or both Lat and Lon must be provided.
        /// </summary>
        public string? Q { get; set; }

        /// <summary>
        /// Latitude. Decimal (-90; 90). Required if Q is not provided.
        /// </summary>
        public double? Lat { get; set; }

        /// <summary>
        /// Longitude. Decimal (-180; 180). Required if Q is not provided.
        /// </summary>
        public double? Lon { get; set; }

        /// <summary>
        /// Units of measurement. Default: "metric".
        /// Options: "standard" (Kelvin, m/s), "metric" (Celsius, m/s), "imperial" (Fahrenheit, mph).
        /// </summary>
        public string Units { get; set; } = "metric";

        /// <summary>
        /// Language for weather description output. Default: "en".
        /// See: https://openweathermap.org/forecast16#multi
        /// </summary>
        public string Lang { get; set; } = "en";

        /// <summary>
        /// Number of days returned (1-16). Default: 7.
        /// </summary>
        public int? Cnt { get; set; }
    }
}
