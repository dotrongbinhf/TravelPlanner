import { useMapsLibrary } from "@vis.gl/react-google-maps";
import { useEffect, useState, useRef } from "react";
import { Input } from "@/components/ui/input";
import { Loader2, MapPin } from "lucide-react";

interface PlaceAutocompleteProps {
  onPlaceSelect: (place: google.maps.places.PlaceResult | null) => void;
  onClose?: () => void;
}

export default function PlaceAutocomplete({
  onPlaceSelect,
  onClose,
}: PlaceAutocompleteProps) {
  const placesLibrary = useMapsLibrary("places");
  const [placesService, setPlacesService] =
    useState<google.maps.places.AutocompleteService | null>(null);
  const [sessionToken, setSessionToken] =
    useState<google.maps.places.AutocompleteSessionToken | null>(null);

  const [value, setValue] = useState("");
  const [predictions, setPredictions] = useState<
    google.maps.places.AutocompletePrediction[]
  >([]);
  const [isLoading, setIsLoading] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!placesLibrary) return;
    setPlacesService(new placesLibrary.AutocompleteService());
    setSessionToken(new placesLibrary.AutocompleteSessionToken());
  }, [placesLibrary]);

  useEffect(() => {
    if (!placesService || !value) {
      setPredictions([]);
      return;
    }

    if (value === "") {
      setPredictions([]);
      return;
    }

    setIsLoading(true);

    const timer = setTimeout(() => {
      if (!placesService) return;

      const request = {
        input: value,
        sessionToken: sessionToken ?? undefined,
      };

      placesService.getPlacePredictions(request, (results, status) => {
        setIsLoading(false);
        if (status === google.maps.places.PlacesServiceStatus.OK && results) {
          setPredictions(results);
        } else {
          setPredictions([]);
        }
      });
    }, 300);

    return () => clearTimeout(timer);
  }, [value, placesService, sessionToken]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        onClose?.();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [onClose]);

  return (
    <div className="relative w-full" ref={containerRef}>
      <div className="relative">
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Search for a place..."
          className="w-full pr-8 h-12 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          autoFocus
        />
        {isLoading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <Loader2 className="animate-spin h-4 w-4 text-gray-400" />
          </div>
        )}
      </div>

      {predictions.length > 0 && (
        <ul className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-md shadow-lg max-h-60 overflow-auto">
          {predictions.map((prediction) => (
            <li
              key={prediction.place_id}
              className="px-4 py-3 hover:bg-gray-100 cursor-pointer flex items-center gap-2 text-sm"
              onClick={() => {
                // Future selection logic
                console.log("Selected", prediction);
              }}
            >
              <MapPin className="h-4 w-4 text-gray-400 shrink-0" />
              <span className="truncate">{prediction.description}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
