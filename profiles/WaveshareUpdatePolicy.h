#pragma once
// Provider-only product identity. Never compile product URLs into shared apps.
namespace WatchUpdate {
constexpr const char *Repository="michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06";
constexpr const char *Product="waveshare-s3-touch-amoled-206";
constexpr const char *AssetPrefix="waveshare-s3-touch-amoled-206";
constexpr bool RequireProduct=true,AllowRuntimeOnly=false;
// The repository exists, but release-index and releases were absent at audit.
// Enable only after published feed/assets and native admission are verified.
constexpr const char *CatalogUrl="";
}
