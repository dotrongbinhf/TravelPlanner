import { useMapsLibrary } from "@vis.gl/react-google-maps";
import { getPlaceByPlaceId, createPlace } from "@/api/place/place";
import { OpenHours, Place } from "@/types/place";
import toast from "react-hot-toast";

export function useEnsurePlace() {
  const placesLib = useMapsLibrary("places");

  const ensurePlaceExists = async (placeId: string): Promise<Place | null> => {
    try {
      // Try to fetch from DB
      const data = await getPlaceByPlaceId(placeId);
      return data;
    } catch (err: any) {
      if (err?.response?.status !== 404 && err?.status !== 404) {
        throw err;
      }
    }

    if (!placesLib) {
      throw new Error("Google Maps Places library not loaded.");
    }

    toast.loading("Fetching place details...", { id: `fetch-${placeId}` });
    try {
      const googlePlace = new placesLib.Place({ id: placeId });

      await googlePlace.fetchFields({
        fields: [
          "displayName",
          "formattedAddress",
          "primaryType",
          "rating",
          "userRatingCount",
          "regularOpeningHours",
          "location",
          "websiteURI",
          "postalAddress",
        ],
      });

      const openHours: OpenHours = {
        monday: [],
        tuesday: [],
        wednesday: [],
        thursday: [],
        friday: [],
        saturday: [],
        sunday: [],
      };

      const dayKeys = [
        "sunday",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
      ] as const;

      googlePlace.regularOpeningHours?.periods?.forEach((p) => {
        if (!p.open || !p.close) return;
        const dayKey = dayKeys[p.open.day];
        const openTime = `${String(p.open.hour).padStart(2, "0")}:${String(
          p.open.minute,
        ).padStart(2, "0")}`;
        const closeTime = `${String(p.close.hour).padStart(2, "0")}:${String(
          p.close.minute,
        ).padStart(2, "0")}`;
        openHours[dayKey].push(`${openTime}-${closeTime}`);
      });

      const newPlace: Place = {
        placeId,
        link: `https://www.google.com/maps/place/?q=place_id:${placeId}`,
        title: googlePlace.displayName ?? "",
        category: googlePlace.primaryType ?? "point_of_interest",
        location: {
          type: "Point",
          coordinates: [
            googlePlace.location?.lng() ?? 0,
            googlePlace.location?.lat() ?? 0,
          ],
        },
        address: googlePlace.formattedAddress ?? "",
        openHours,
        website: googlePlace.websiteURI ?? "",
        reviewCount: googlePlace.userRatingCount ?? 0,
        reviewRating: googlePlace.rating ?? 0,
        reviewsPerRating: {},
        cid: "",
        description: "",
        thumbnail: "https://placehold.co/600x400?text=No+Image",
        images: [],
        userReviews: [],
        createdDate: new Date().toISOString(),
        modifiedDate: new Date().toISOString(),
        id: "", // backend will generate
      };

      // Save to DB
      const createdPlace = await createPlace(newPlace);
      toast.dismiss(`fetch-${placeId}`);
      return createdPlace;
    } catch (googleErr) {
      console.error("Google fetch or DB save failed:", googleErr);
      toast.error("Failed to fetch place details", { id: `fetch-${placeId}` });
      throw googleErr;
    }
  };

  return { ensurePlaceExists };
}
