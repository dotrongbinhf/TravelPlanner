using System.Text.Json.Serialization;

namespace dotnet.Dtos.ExternalApi
{
    /// <summary>
    /// Response DTO for OpenWeatherMap Daily Forecast 16 Days API.
    /// Endpoint: GET /data/2.5/forecast/daily
    /// Returns daily weather forecast data for up to 16 days.
    /// </summary>
    public class WeatherResponseDto
    {
        /// <summary>Error message set by the service when the API call fails. Not from API.</summary>
        [JsonIgnore]
        public string? Error { get; set; }

        /// <summary>City information.</summary>
        public DailyForecastCityDto? City { get; set; }

        /// <summary>Internal parameter (HTTP status code as string, e.g., "200").</summary>
        public string? Cod { get; set; }

        /// <summary>Internal parameter.</summary>
        public double? Message { get; set; }

        /// <summary>Number of days returned.</summary>
        public int? Cnt { get; set; }

        /// <summary>List of daily forecast data points.</summary>
        public List<DailyForecastItemDto>? List { get; set; }
    }

    /// <summary>A single day forecast data point.</summary>
    public class DailyForecastItemDto
    {
        /// <summary>Time of data forecasted, unix, UTC.</summary>
        public long? Dt { get; set; }

        /// <summary>Sunrise time, unix, UTC.</summary>
        public long? Sunrise { get; set; }

        /// <summary>Sunset time, unix, UTC.</summary>
        public long? Sunset { get; set; }

        /// <summary>Temperature details for the day (day, min, max, night, eve, morn).</summary>
        public DailyTempDto? Temp { get; set; }

        /// <summary>Human perception of weather temperature (day, night, eve, morn).</summary>
        public DailyFeelsLikeDto? FeelsLike { get; set; }

        /// <summary>Atmospheric pressure on the sea level, hPa.</summary>
        public int? Pressure { get; set; }

        /// <summary>Humidity, %.</summary>
        public int? Humidity { get; set; }

        /// <summary>Weather condition details.</summary>
        public List<WeatherConditionDto>? Weather { get; set; }

        /// <summary>Wind speed. Unit depends on 'units' parameter.</summary>
        public double? Speed { get; set; }

        /// <summary>Wind direction, degrees (meteorological).</summary>
        public int? Deg { get; set; }

        /// <summary>Wind gust. Unit depends on 'units' parameter.</summary>
        public double? Gust { get; set; }

        /// <summary>Cloudiness, %.</summary>
        public int? Clouds { get; set; }

        /// <summary>Probability of precipitation (0 to 1).</summary>
        public double? Pop { get; set; }

        /// <summary>Precipitation volume, mm. Only present when rain data is available.</summary>
        public double? Rain { get; set; }

        /// <summary>Snow volume, mm. Only present when snow data is available.</summary>
        public double? Snow { get; set; }
    }

    /// <summary>Daily temperature breakdown.</summary>
    public class DailyTempDto
    {
        /// <summary>Day temperature.</summary>
        public double? Day { get; set; }

        /// <summary>Min daily temperature.</summary>
        public double? Min { get; set; }

        /// <summary>Max daily temperature.</summary>
        public double? Max { get; set; }

        /// <summary>Night temperature.</summary>
        public double? Night { get; set; }

        /// <summary>Evening temperature.</summary>
        public double? Eve { get; set; }

        /// <summary>Morning temperature.</summary>
        public double? Morn { get; set; }
    }

    /// <summary>Daily "feels like" temperature breakdown.</summary>
    public class DailyFeelsLikeDto
    {
        /// <summary>Day temperature.</summary>
        public double? Day { get; set; }

        /// <summary>Night temperature.</summary>
        public double? Night { get; set; }

        /// <summary>Evening temperature.</summary>
        public double? Eve { get; set; }

        /// <summary>Morning temperature.</summary>
        public double? Morn { get; set; }
    }

    /// <summary>City information in daily forecast response.</summary>
    public class DailyForecastCityDto
    {
        /// <summary>City ID.</summary>
        public int? Id { get; set; }

        /// <summary>City name.</summary>
        public string? Name { get; set; }

        /// <summary>City geo location (lat, lon).</summary>
        public WeatherCoordDto? Coord { get; set; }

        /// <summary>Country code (e.g., "GB", "US").</summary>
        public string? Country { get; set; }

        /// <summary>City population.</summary>
        public int? Population { get; set; }

        /// <summary>Shift in seconds from UTC.</summary>
        public int? Timezone { get; set; }
    }

    /// <summary>Geographic coordinates.</summary>
    public class WeatherCoordDto
    {
        /// <summary>Latitude.</summary>
        public double? Lat { get; set; }

        /// <summary>Longitude.</summary>
        public double? Lon { get; set; }
    }

    /// <summary>Weather condition.</summary>
    public class WeatherConditionDto
    {
        /// <summary>Weather condition ID. See: https://openweathermap.org/weather-conditions</summary>
        public int? Id { get; set; }

        /// <summary>Group of weather parameters (Rain, Snow, Clouds, etc.).</summary>
        public string? Main { get; set; }

        /// <summary>Weather condition description within the group.</summary>
        public string? Description { get; set; }

        /// <summary>Weather icon ID. URL: https://openweathermap.org/img/wn/{icon}@2x.png</summary>
        public string? Icon { get; set; }
    }
}
