using dotnet.Dtos.ExternalApi;
using dotnet.Entites;

namespace dotnet.Interfaces
{
    public interface IExternalApiService
    {
        Task<HotelSearchResponseDto> GetHotelsAsync(HotelSearchRequestDto request);
        Task<FlightSearchResponseDto> GetFlightsAsync(FlightSearchRequestDto request);
        Task<AirportAutocompleteResponseDto> SearchAirportAutocompleteAsync(AirportAutocompleteRequestDto request);
        Task<WeatherResponseDto> GetDailyForecastAsync(WeatherRequestDto request);
        Task<Place?> GetPlaceDetailsAsync(string placeId);
    }
}
