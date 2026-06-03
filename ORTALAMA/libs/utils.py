def gimbal_turn_calculator(camera_pos: tuple, camera_res: tuple, camera_fov: tuple=(62.2, 48.8)):
    return camera_fov[0] / 2 - ((camera_fov[0] * camera_pos[0]) / camera_res[0]), camera_fov[1] / 2 - ((camera_fov[1] * camera_pos[1]) / camera_res[1])

def gimbal_new_angles(gimbal_pos: tuple, values: tuple, gimbal_min: tuple, gimbal_max: tuple):
    new_values = [gimbal_pos[0], gimbal_pos[1]]

    if gimbal_pos[0] + values[0] <= gimbal_max[0] and gimbal_pos[0] + values[0] >= gimbal_min[0]:
        new_values[0] = gimbal_pos[0] + values[0]

    if gimbal_pos[1] + values[1] <= gimbal_max[1] and gimbal_pos[1] + values[1] >= gimbal_min[1]:
        new_values[1] = gimbal_pos[1] + values[1]
    
    print("new values: ", new_values)
    return (new_values[0], new_values[1])

def joystick_value_split(line: str):
    joystick_values = {"x": 0, "y": 0, "joy_btn": 0, "btn1": 0, "btn2": 0}

    if line is None or line == "":
        return None
    if len(line.split("|")) != 5:
        return None

    for l in line.split("|"):
        if len(l.split(":")) != 2:
            return None
    
    x = int(line.split("|")[0].split(":")[1].strip()) 
    y = int(line.split("|")[1].split(":")[1].strip()) 

    if x > 800:
        joystick_values["x"] = 1
    elif x < 200:
        joystick_values["x"] = -1
    else:
        joystick_values["x"] = 0
    if y > 800:
        joystick_values["y"] = 1
    elif y < 200:
        joystick_values["y"] = -1
    else:
        joystick_values["y"] = 0
    
    joystick_values["joy_btn"] = int(line.split("|")[2].split(":")[1].strip())
    joystick_values["btn1"] = int(line.split("|")[3].split(":")[1].strip())
    joystick_values["btn2"] = int(line.split("|")[4].split(":")[1].strip())

    return joystick_values

def calc_angle_distance(distance, angle):
    import math

    return distance * math.cos(math.radians(angle))