import json
import requests
import generatemap
import osrm_plus

# Load JSON data
with open("test.json", "r") as file:
    data = json.load(file)

# Separate CM and PM tasks
cm_data = [job for job in data if job["task_type"] == "CM"]
pm_data = [job for job in data if job["task_type"] == "PM"]

def process_function(data):
    job_coordinates = [
        f"{job_data['longitude']},{job_data['latitude']}" for job_data in data
    ]
    osrm_route_service = "http://146.196.106.202:20073/route/v1/driving/"
    route_info = osrm_plus.distances_and_durations(
        job_coordinates, osrm_route_service=osrm_route_service, include_speed=True
    )
    distances = route_info["distances"]
    durations = route_info["durations"]

    listed = [0]
    size = len(job_coordinates)

    minRange = []
    minDuration = []
    minRange2 = [0 for i in range(size)]
    minDuration2 = [0 for i in range(size)]
    myJob = [(0, 0) for x in range(size)]

    x = 0
    k = 0
    l = 0
    for i in range(0, size):
        for j in range(0, size):
            if k == j:
                continue
            elif distances[k, j] == 0:
                if j in listed:
                    continue
                minRange.append(distances[k, j])
                minDuration.append(durations[k, j])
                listed.append(j)
                k = j
                break
            else:
                if j in listed:
                    continue

                elif len(minRange) == 0:
                    minRange.append(distances[k, j])
                    minDuration.append(durations[k, j])
                    listed.append(j)

                elif i > l:
                    minRange.append(distances[k, j])
                    minDuration.append(durations[k, j])
                    listed.append(j)
                    l += 1

                elif minRange[-1] > distances[k, j]:
                    minRange.pop()
                    minDuration.pop()
                    listed.pop()
                    minRange.append(distances[k, j])
                    minDuration.append(durations[k, j])
                    listed.append(j)
                    x = j

        k = x

    listed.pop(0)
    sorted_dict = {}
    if not sorted_dict:
        value = data[0]  # First item
        value["duration"] = 0
        sorted_dict[0] = value  # index becomes key
    for i in range(len(data) - 1):
        index = listed[i]
        value = data[index]
        value["duration"] = minDuration[i]
        sorted_dict[index] = value

    return sorted_dict

def get_osrm_distances(cm_data, pm_data):
    coordinates = [
        f"{task['longitude']},{task['latitude']}" for task in cm_data + pm_data
    ]
    coordinates_str = ";".join(coordinates)

    osrm_table_service = "http://146.196.106.202:20073/table/v1/driving/"

    response = requests.get(
        f"{osrm_table_service}{coordinates_str}?annotations=distance"
    )
    data = response.json()

    distance_matrix = data["distances"]

    cm_count = len(cm_data)
    pm_count = len(pm_data)

    cm_pm_distances = [row[cm_count:] for row in distance_matrix[:cm_count]]

    return cm_pm_distances

def get_osrm_durations(cm_data, pm_data):
    coordinates = [
        f"{task['longitude']},{task['latitude']}" for task in cm_data + pm_data
    ]
    coordinates_str = ";".join(coordinates)

    osrm_table_service = "http://146.196.106.202:20073/table/v1/driving/"

    response = requests.get(
        f"{osrm_table_service}{coordinates_str}?annotations=duration"
    )
    data = response.json()

    duration_matrix = data["durations"]

    cm_count = len(cm_data)
    pm_count = len(pm_data)

    cm_pm_durations = [row[cm_count:] for row in duration_matrix[:cm_count]]

    return cm_pm_durations

def generate_osrm_route(route, osrm_route_service="http://146.196.106.202:20073/route/v1/driving/"):
    coordinates = ";".join(
        [f"{task['longitude']},{task['latitude']}" for task in route]
    )
    url = f"{osrm_route_service}{coordinates}?overview=full&geometries=geojson"
    response = requests.get(url)
    route_data = response.json()
    return route_data["routes"][0]["geometry"]

def integrate_pm_tasks(cm_route, pm_tasks, osrm_distances, osrm_durations, range_km):
    final_route = []
    segment_durations = []
    segment_distances = []
    current_time = 0
    max_work_time = 720  # 12 hours in minutes

    cm_route_keys = list(cm_route.keys())

    task_groups = {}

    # Process all CM tasks first
    for cm_task_index, cm_key in enumerate(cm_route_keys):
        if current_time >= max_work_time:
            break
        cm_task = cm_route[cm_key]
        cm_task["arrival_time"] = current_time
        final_route.append(cm_task)

        loc_key = (cm_task['latitude'], cm_task['longitude'])
        if loc_key not in task_groups:
            task_groups[loc_key] = []
        task_groups[loc_key].append(cm_task)

        if cm_task_index < len(osrm_durations) and cm_task_index < len(osrm_durations[cm_task_index]):
            segment_durations.append(osrm_durations[cm_task_index][cm_task_index])
            segment_distances.append(osrm_distances[cm_task_index][cm_task_index])

        current_time += cm_task["duration"] / 60  # Convert to minutes

    # Add PM tasks if there's still time
    for pm_index, pm_task in enumerate(pm_tasks):
        if current_time >= max_work_time:
            break
        best_time = float("inf")
        best_pm_index = -1
        for cm_task_index, cm_key in enumerate(cm_route_keys):
            travel_time = osrm_durations[cm_task_index][pm_index] / 60
            travel_distance = osrm_distances[cm_task_index][pm_index] / 1000

            if travel_distance <= range_km and travel_time < best_time:
                best_time = travel_time
                best_pm_index = pm_index

        if best_pm_index != -1:
            pm_task = pm_tasks.pop(best_pm_index)
            pm_duration = pm_task.get("duration", 10) / 60  # Default 10 minutes

            if current_time + best_time + pm_duration <= max_work_time:
                current_time += best_time
                pm_task["arrival_time"] = current_time
                current_time += pm_duration

                loc_key = (pm_task['latitude'], pm_task['longitude'])
                if loc_key not in task_groups:
                    task_groups[loc_key] = []
                task_groups[loc_key].append(pm_task)

                final_route.append(pm_task)
                segment_durations.append(best_time * 60)  # Convert back to seconds
                segment_distances.append(osrm_distances[cm_task_index][pm_index])

    log = []
    for i in range(len(final_route)):
        log.append({
            "task": final_route[i],
            "distance": segment_distances[i],
            "duration": segment_durations[i],
        })

    with open("log.json", "w") as file:
        json.dump(log, file)

    road_geometry = generate_osrm_route(final_route)

    with open("road_geometry.json", "w") as file:
        json.dump(road_geometry, file)

    if road_geometry is None:
        print("Route generation failed. No geometry data available.")
    else:
        generatemap.visualize_route(
            final_route, road_geometry, segment_durations, segment_distances, task_groups
        )

    return final_route, road_geometry, segment_durations, segment_distances, task_groups

cm_route = process_function(cm_data)
osrm_distances = get_osrm_distances(cm_data, pm_data)
osrm_durations = get_osrm_durations(cm_data, pm_data)

with open("pm_data.json", "w") as file:
    json.dump(pm_data, file)

with open("cm_data.json", "w") as file:
    json.dump(cm_data, file)

with open("osrm_distances.json", "w") as file:
    json.dump(osrm_distances, file)

with open("osrm_durations.json", "w") as file:
    json.dump(osrm_durations, file)

final_route, road_geometry, durations, distances, task_groups = integrate_pm_tasks(
    cm_route, pm_data, osrm_distances, osrm_durations, range_km=2
)

generatemap.visualize_route(final_route, road_geometry, durations, distances, task_groups)

print("Map generated successfully!")
