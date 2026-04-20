using System.Text.Json;
using System.Web;
using dotnet.Dtos.ExternalApi;
using dotnet.Entites;
using Microsoft.Extensions.Configuration;

namespace dotnet.Services
{
    public class ExternalApiService : dotnet.Interfaces.IExternalApiService
    {
        private readonly HttpClient _httpClient;
        private readonly IConfiguration _configuration;

        /// <summary>
        /// JSON options for SerpApi and OpenWeatherMap responses (snake_case).
        /// .NET 8 supports JsonNamingPolicy.SnakeCaseLower natively.
        /// </summary>
        private static readonly JsonSerializerOptions _snakeCaseOptions = new()
        {
            PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
            PropertyNameCaseInsensitive = true,
        };

        /// <summary>
        /// JSON options for AeroDataBox / RapidAPI responses (camelCase).
        /// </summary>
        private static readonly JsonSerializerOptions _camelCaseOptions = new()
        {
            PropertyNameCaseInsensitive = true,
        };

        public ExternalApiService(HttpClient httpClient, IConfiguration configuration)
        {
            _httpClient = httpClient;
            _configuration = configuration;
        }

        // ======================== HOTEL (SerpApi) ========================

        public async Task<HotelSearchResponseDto> GetHotelsAsync(HotelSearchRequestDto request)
        {
            var apiKey = _configuration["ExternalApis:SerpApi:ApiKey"];

            var qb = HttpUtility.ParseQueryString(string.Empty);
            qb["engine"] = "google_hotels";
            qb["api_key"] = apiKey;

            // Required
            qb["q"] = request.Q;
            qb["check_in_date"] = request.CheckInDate;
            qb["check_out_date"] = request.CheckOutDate;

            // Defaults
            qb["adults"] = request.Adults.ToString();
            qb["children"] = request.Children.ToString();
            qb["gl"] = request.Gl;
            qb["hl"] = request.Hl;
            qb["currency"] = request.Currency;

            // Optional
            if (!string.IsNullOrEmpty(request.ChildrenAges)) qb["children_ages"] = request.ChildrenAges;
            if (request.SortBy.HasValue) qb["sort_by"] = request.SortBy.Value.ToString();
            if (request.MinPrice.HasValue) qb["min_price"] = request.MinPrice.Value.ToString();
            if (request.MaxPrice.HasValue) qb["max_price"] = request.MaxPrice.Value.ToString();
            if (!string.IsNullOrEmpty(request.PropertyTypes)) qb["property_types"] = request.PropertyTypes;
            if (!string.IsNullOrEmpty(request.Amenities)) qb["amenities"] = request.Amenities;
            if (request.Rating.HasValue) qb["rating"] = request.Rating.Value.ToString();
            if (!string.IsNullOrEmpty(request.Brands)) qb["brands"] = request.Brands;
            if (!string.IsNullOrEmpty(request.HotelClass)) qb["hotel_class"] = request.HotelClass;
            if (request.FreeCancellation == true) qb["free_cancellation"] = "true";
            if (request.SpecialOffers == true) qb["special_offers"] = "true";
            if (request.EcoCertified == true) qb["eco_certified"] = "true";
            if (request.VacationRentals == true) qb["vacation_rentals"] = "true";
            if (request.Bedrooms.HasValue) qb["bedrooms"] = request.Bedrooms.Value.ToString();
            if (request.Bathrooms.HasValue) qb["bathrooms"] = request.Bathrooms.Value.ToString();

            var response = await _httpClient.GetAsync($"https://serpapi.com/search.json?{qb}");

            if (!response.IsSuccessStatusCode)
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                return new HotelSearchResponseDto { Error = $"External API Error: {errorContent}" };
            }

            var content = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<HotelSearchResponseDto>(content, _snakeCaseOptions)
                   ?? new HotelSearchResponseDto();
        }

        // ======================== FLIGHT (SerpApi) ========================

        public async Task<FlightSearchResponseDto> GetFlightsAsync(FlightSearchRequestDto request)
        {
            var apiKey = _configuration["ExternalApis:SerpApi:ApiKey"];

            var qb = HttpUtility.ParseQueryString(string.Empty);
            qb["engine"] = "google_flights";
            qb["api_key"] = apiKey;

            // Required
            qb["departure_id"] = request.DepartureId;
            qb["arrival_id"] = request.ArrivalId;
            qb["outbound_date"] = request.OutboundDate;

            // Defaults
            qb["type"] = request.Type.ToString();
            qb["travel_class"] = request.TravelClass.ToString();
            qb["adults"] = request.Adults.ToString();
            qb["children"] = request.Children.ToString();
            qb["infants_in_seat"] = request.InfantsInSeat.ToString();
            qb["infants_on_lap"] = request.InfantsOnLap.ToString();
            qb["currency"] = request.Currency;
            qb["hl"] = request.Hl;
            qb["gl"] = request.Gl;

            // Optional
            if (!string.IsNullOrEmpty(request.ReturnDate)) qb["return_date"] = request.ReturnDate;
            if (!string.IsNullOrEmpty(request.MultiCityJson)) qb["multi_city_json"] = request.MultiCityJson;
            if (request.SortBy.HasValue) qb["sort_by"] = request.SortBy.Value.ToString();
            if (request.Stops.HasValue) qb["stops"] = request.Stops.Value.ToString();
            if (!string.IsNullOrEmpty(request.ExcludeAirlines)) qb["exclude_airlines"] = request.ExcludeAirlines;
            if (!string.IsNullOrEmpty(request.IncludeAirlines)) qb["include_airlines"] = request.IncludeAirlines;
            if (request.Bags.HasValue) qb["bags"] = request.Bags.Value.ToString();
            if (request.MaxPrice.HasValue) qb["max_price"] = request.MaxPrice.Value.ToString();
            if (!string.IsNullOrEmpty(request.OutboundTimes)) qb["outbound_times"] = request.OutboundTimes;
            if (!string.IsNullOrEmpty(request.ReturnTimes)) qb["return_times"] = request.ReturnTimes;
            if (request.Emissions.HasValue) qb["emissions"] = request.Emissions.Value.ToString();
            if (!string.IsNullOrEmpty(request.LayoverDuration)) qb["layover_duration"] = request.LayoverDuration;
            if (!string.IsNullOrEmpty(request.ExcludeConns)) qb["exclude_conns"] = request.ExcludeConns;
            if (request.MaxDuration.HasValue) qb["max_duration"] = request.MaxDuration.Value.ToString();
            if (!string.IsNullOrEmpty(request.DepartureToken)) qb["departure_token"] = request.DepartureToken;
            //if (!string.IsNullOrEmpty(request.BookingToken)) qb["booking_token"] = request.BookingToken;

            var response = await _httpClient.GetAsync($"https://serpapi.com/search.json?{qb}");

            if (!response.IsSuccessStatusCode)
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                return new FlightSearchResponseDto { Error = $"External API Error: {errorContent}" };
            }

            var content = await response.Content.ReadAsStringAsync();
            var result = JsonSerializer.Deserialize<FlightSearchResponseDto>(content, _snakeCaseOptions)
                         ?? new FlightSearchResponseDto();

            // Extract google_flights_url from search_metadata
            if (result.SearchMetadata?.GoogleFlightsUrl != null)
            {
                result.GoogleFlightsUrl = result.SearchMetadata.GoogleFlightsUrl;
            }

            return result;
        }

        // ======================== AIRPORT (AeroDataBox / RapidAPI) ========================

        public async Task<AirportSearchResponseDto> SearchAirportsAsync(AirportSearchByLocationRequestDto request)
        {
            var apiKey = _configuration["ExternalApis:RapidApi:ApiKey"];
            var apiHost = _configuration["ExternalApis:RapidApi:ApiHost"];

            var lat = request.Lat.ToString(System.Globalization.CultureInfo.InvariantCulture);
            var lon = request.Lon.ToString(System.Globalization.CultureInfo.InvariantCulture);

            var url = $"https://aerodatabox.p.rapidapi.com/airports/search/location/{lat}/{lon}/km/{request.RadiusKm}/{request.Limit}?withFlightInfoOnly={request.WithFlightInfoOnly.ToString().ToLower()}";

            var requestMessage = new HttpRequestMessage
            {
                Method = HttpMethod.Get,
                RequestUri = new Uri(url),
                Headers =
                {
                    { "x-rapidapi-key", apiKey },
                    { "x-rapidapi-host", apiHost },
                },
            };

            var response = await _httpClient.SendAsync(requestMessage);

            if (!response.IsSuccessStatusCode)
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                return new AirportSearchResponseDto { Error = $"External API Error: {errorContent}" };
            }

            var content = await response.Content.ReadAsStringAsync();

            // AeroDataBox location search returns { "items": [ ... ] }
            var result = JsonSerializer.Deserialize<AirportSearchResponseDto>(content, _camelCaseOptions);
            return result ?? new AirportSearchResponseDto();
        }

        // ======================== WEATHER (OpenWeatherMap 2.5 - Daily Forecast 16 Days) ========================

        /// <summary>
        /// Daily Forecast 16 Days - /data/2.5/forecast/daily
        /// API Reference: https://openweathermap.org/forecast16
        /// </summary>
        public async Task<WeatherResponseDto> GetDailyForecastAsync(WeatherRequestDto request)
        {
            var apiKey = _configuration["ExternalApis:OpenWeatherMap:ApiKey"];
            var qb = HttpUtility.ParseQueryString(string.Empty);

            if (!string.IsNullOrEmpty(request.Q))
            {
                qb["q"] = request.Q;
            }
            else if (request.Lat.HasValue && request.Lon.HasValue)
            {
                qb["lat"] = request.Lat.Value.ToString(System.Globalization.CultureInfo.InvariantCulture);
                qb["lon"] = request.Lon.Value.ToString(System.Globalization.CultureInfo.InvariantCulture);
            }

            qb["units"] = request.Units;
            qb["lang"] = request.Lang;
            qb["appid"] = apiKey;

            if (request.Cnt.HasValue) qb["cnt"] = request.Cnt.Value.ToString();

            var response = await _httpClient.GetAsync($"https://api.openweathermap.org/data/2.5/forecast/daily?{qb}");

            if (!response.IsSuccessStatusCode)
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                return new WeatherResponseDto { Error = $"External API Error: {errorContent}" };
            }

            var content = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<WeatherResponseDto>(content, _snakeCaseOptions)
                   ?? new WeatherResponseDto();
        }

        // ======================== GOOGLE PLACES (New) — Place Details ========================
        // Enterprise SKU

        /// <summary>
        /// Fetch place details from Google Places API (New) and return as a Place entity.
        /// Uses GET places/{placeId} with X-Goog-FieldMask for cost optimization.
        /// Reference: https://developers.google.com/maps/documentation/places/web-service/place-details
        /// </summary>
        public async Task<Place?> GetPlaceDetailsAsync(string placeId)
        {
            var apiKey = _configuration["ExternalApis:GoogleMaps:ApiKey"];
            if (string.IsNullOrEmpty(apiKey))
            {
                return null;
            }

            var url = $"https://places.googleapis.com/v1/places/{placeId}";
            var fieldMask = "id,displayName,formattedAddress,location,types,rating,userRatingCount,regularOpeningHours,websiteUri,googleMapsUri";

            var request = new HttpRequestMessage(HttpMethod.Get, url);
            request.Headers.Add("X-Goog-Api-Key", apiKey);
            request.Headers.Add("X-Goog-FieldMask", fieldMask);

            var response = await _httpClient.SendAsync(request);
            if (!response.IsSuccessStatusCode) return null;

            var content = await response.Content.ReadAsStringAsync();
            using var doc = JsonDocument.Parse(content);
            var result = doc.RootElement;

            // Check for error response
            if (result.TryGetProperty("error", out _)) return null;

            // Parse location (New API: { "latitude": ..., "longitude": ... })
            double lat = 0, lng = 0;
            if (result.TryGetProperty("location", out var location))
            {
                lat = location.TryGetProperty("latitude", out var latProp) ? latProp.GetDouble() : 0;
                lng = location.TryGetProperty("longitude", out var lngProp) ? lngProp.GetDouble() : 0;
            }

            // Parse opening hours (New API: regularOpeningHours.periods[].open/close.hour/minute)
            var openHours = new OpenHours();
            string[] dayKeys = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];

            if (result.TryGetProperty("regularOpeningHours", out var regHours) &&
                regHours.TryGetProperty("periods", out var periods))
            {
                foreach (var period in periods.EnumerateArray())
                {
                    if (!period.TryGetProperty("open", out var openInfo) ||
                        !period.TryGetProperty("close", out var closeInfo))
                        continue;

                    var dayIdx = openInfo.TryGetProperty("day", out var dayProp) ? dayProp.GetInt32() : -1;
                    if (dayIdx < 0 || dayIdx >= 7) continue;

                    var oh = openInfo.TryGetProperty("hour", out var ohProp) ? ohProp.GetInt32() : 0;
                    var om = openInfo.TryGetProperty("minute", out var omProp) ? omProp.GetInt32() : 0;
                    var ch = closeInfo.TryGetProperty("hour", out var chProp) ? chProp.GetInt32() : 23;
                    var cm = closeInfo.TryGetProperty("minute", out var cmProp) ? cmProp.GetInt32() : 59;
                    var timeRange = $"{oh:D2}:{om:D2}-{ch:D2}:{cm:D2}";

                    switch (dayKeys[dayIdx])
                    {
                        case "sunday": openHours.Sunday.Add(timeRange); break;
                        case "monday": openHours.Monday.Add(timeRange); break;
                        case "tuesday": openHours.Tuesday.Add(timeRange); break;
                        case "wednesday": openHours.Wednesday.Add(timeRange); break;
                        case "thursday": openHours.Thursday.Add(timeRange); break;
                        case "friday": openHours.Friday.Add(timeRange); break;
                        case "saturday": openHours.Saturday.Add(timeRange); break;
                    }
                }
            }

            // Get category (first type)
            var category = "point_of_interest";
            if (result.TryGetProperty("types", out var types))
            {
                var firstType = types.EnumerateArray().FirstOrDefault();
                if (firstType.ValueKind == JsonValueKind.String)
                    category = firstType.GetString() ?? category;
            }

            // displayName is { "text": "...", "languageCode": "..." }
            var title = "";
            if (result.TryGetProperty("displayName", out var displayName) &&
                displayName.TryGetProperty("text", out var textProp))
            {
                title = textProp.GetString() ?? "";
            }

            return new Place
            {
                PlaceId = placeId,
                Link = result.TryGetProperty("googleMapsUri", out var uriProp) ? uriProp.GetString() ?? "" : $"https://www.google.com/maps/place/?q=place_id:{placeId}",
                Title = title,
                Category = category,
                Location = new GeoJson
                {
                    Type = "Point",
                    Coordinates = [lng, lat]
                },
                Address = result.TryGetProperty("formattedAddress", out var addrProp) ? addrProp.GetString() ?? "" : "",
                OpenHours = openHours,
                Website = result.TryGetProperty("websiteUri", out var webProp) ? webProp.GetString() ?? "" : "",
                ReviewCount = result.TryGetProperty("userRatingCount", out var rcProp) ? rcProp.GetInt32() : 0,
                ReviewRating = result.TryGetProperty("rating", out var rrProp) ? rrProp.GetDouble() : 0,
                ReviewsPerRating = new Dictionary<int, int>(),
                Cid = "",
                Description = "",
                Thumbnail = "",
                Images = [],
                UserReviews = [],
                CreatedDate = DateTime.UtcNow,
                ModifiedDate = DateTime.UtcNow,
            };
        }
    }
}

