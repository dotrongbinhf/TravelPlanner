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
