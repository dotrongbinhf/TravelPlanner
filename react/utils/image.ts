export const getResizedImageUrl = (
  url: string,
  width?: number,
  height?: number,
) => {
  if (!url) return "";
  if (!width && !height) return url;
  if (width && !height)
    return url.replace(
      "/upload/",
      `/upload/c_fill,w_${width},f_auto,q_auto,dpr_auto/`,
    );
  if (!width && height)
    return url.replace(
      "/upload/",
      `/upload/c_fill,h_${height},f_auto,q_auto,dpr_auto/`,
    );
  return url.replace(
    "/upload/",
    `/upload/c_fill,w_${width},h_${height},f_auto,q_auto,dpr_auto/`,
  );
};

export const getInitials = (name?: string, username?: string) => {
  const displayName = name?.trim() || username?.trim() || "";
  if (!displayName) return "U";

  const parts = displayName.split(/\s+/);
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  return (parts[0][0] + parts[1][0]).toUpperCase();
};
