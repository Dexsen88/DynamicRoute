import folium
import math

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on the Earth's surface using Haversine formula."""
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r

def visualize_route(route, road_geometry, durations, distances, task_groups):
    """Visualize route on a map with distance and duration information."""
    # Initialize the map centered on the first location
    map_center = [route[0]['latitude'], route[0]['longitude']]
    folium_map = folium.Map(location=map_center, zoom_start=13)

    # Group tasks by location and add markers
    for loc, tasks in task_groups.items():
        color = 'red' if len(tasks) > 1 else ('green' if tasks[0]['task_type'] == 'CM' else 'blue')
        
        # Construct the popup content
        task_details = ''.join([f"{task['location_name']}, Arrival Time: {task['arrival_time']} min<br>" for task in tasks])
        popup = f"Tasks at this location:<br>{task_details}"

        # Add marker to the map
        folium.Marker(
            location=[loc[0], loc[1]],
            popup=popup,
            icon=folium.Icon(color=color)
        ).add_to(folium_map)

    # Add the road_geometry to the map with a fixed blue color
    if road_geometry:
        folium.PolyLine(
            locations=[(point[1], point[0]) for point in road_geometry['coordinates']],
            color="blue",
            weight=5,
            opacity=0.7
        ).add_to(folium_map)

    # Prepare and add the route summary to the map
    route_summary = "<div style='font-size: 14px; color: black;'><b>Route Information:</b><br>"
    for i in range(1, len(route)):
        if i-1 < len(distances) and i-1 < len(durations):
            # Calculate distance using Haversine formula
            distance = haversine(
                route[i-1]['latitude'], route[i-1]['longitude'],
                route[i]['latitude'], route[i]['longitude']
            )
            duration = durations[i-1] / 60  # Convert seconds to minutes

            # Display segment distance and time on the map
            folium.Marker(
                location=[(route[i-1]['latitude'] + route[i]['latitude']) / 2,
                          (route[i-1]['longitude'] + route[i]['longitude']) / 2],
                popup=f"{distance:.2f} km, {duration:.2f} min",
                icon=folium.DivIcon(html=f"<div style='font-size: 12px; color: red;'>{distance:.2f} km, {duration:.2f} min</div>")
            ).add_to(folium_map)
            
            # Add information to the summary
            route_summary += f"{route[i-1]['location_name']} --> {route[i]['location_name']} --> {duration:.2f} mins & {distance:.2f} km<br>"

    route_summary += "</div>"

    # Add the summary to the map
    folium_map.get_root().html.add_child(folium.Element(route_summary))

    # Save the map to an HTML file
if False:
    folium_map.save("dynamic_route_map.html")
    print("Map generated successfully!")

