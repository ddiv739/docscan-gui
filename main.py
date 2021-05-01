import PySimpleGUI as sg
import cv2
import numpy as np
from PIL import ImageGrab
"""
    Demo - Drag a rectangle to draw it
    This demo shows how to use a Graph Element to (optionally) display an image and then use the
    mouse to "drag a rectangle".  This is sometimes called a rubber band and is an operation you
    see in things like editors
"""
def get_drag_fig(graph,points,x,y):
    drag_figures = graph.get_figures_at_location((x,y))

    #we only want to drag one at a time
    for fig in drag_figures:
        if fig in points.keys():
            return fig

    return False
        
def draw_poly(graph,points):
    priors = []
    lpoints = list(points.values())
    for i in range(len(lpoints)-1):
        priors.append(graph.draw_line(lpoints[i],lpoints[i+1],color='red'))
    priors.append(graph.draw_line(lpoints[0],lpoints[-1],color='red'))

    return priors

def apply_ipm(cap, points):
    #probably fine to leave dtype as int but keep consistent with dst for now
    if type(points) == dict:
        src = np.array([list(y) for y in points.values()],dtype='float32')
    else:
        src = np.array([list(y) for y in points],dtype='float32')
    (tl, tr, br, bl) = src
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    # ...and now for the height of our new image
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    # take the maximum of the width and height values to reach
    # our final dimensions
    maxWidth = max(int(widthA), int(widthB))
    maxHeight = max(int(heightA), int(heightB))
    # construct our destination points which will be used to
    # map the screen to a top-down, "birds eye" view
    dst =  np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]], dtype = "float32")

    M = cv2.getPerspectiveTransform(src, dst)
    warp = cv2.warpPerspective(cap, M, (maxWidth, maxHeight))

    return warp

def save_scaled_cap_as_file(orig_cap,points,scaled_width,scaled_height):
    orig_h,orig_w,_ = orig_cap.shape
    points = [(x[0]*orig_w/scaled_width,x[1]*orig_h/scaled_height)  for x in points.values()]
    out_cap = apply_ipm(orig_cap,points)
    cv2.imwrite('test.png',out_cap)

# Get the folder containing the images from the user
fp = sg.popup_get_file('Image file to open', default_path='')
if not fp:
    sg.popup_cancel('Cancelling')
    raise SystemExit()

orig_cap = cap = cv2.imread(fp)

#TODO TODO if we resize we should save the original mat and coords to prevent downscaling of output
max_size = 600 
if any(x > max_size for x in cap.shape):
    rscl_fctr_y = cap.shape[0]//max_size
    rscl_fctr_x = cap.shape[1]//max_size
    orig_cap = cap
    cap = cv2.resize(cap,dsize=(cap.shape[0]//rscl_fctr_y,cap.shape[1]//rscl_fctr_x))

# cap = cv2.resize(cap,(500,500))
image_file=cv2.imencode('.png', cap)[1].tobytes()

#Points are intentionally non-sequential to match OPENCV warp ordering to be tl tr br bl
#not necessary but makes subsequent transform easier
points = {2:(20,20),
            5:(cap.shape[0]//2,20),
            3:(cap.shape[0]//2,cap.shape[1]//2),
            4:(20,cap.shape[1]//2),
        }
layout = [
        [
            sg.Graph(
                canvas_size=(cap.shape[1], cap.shape[0]),
                graph_bottom_left=(0,cap.shape[0]),
                graph_top_right=(cap.shape[1], 0),
                key="-GRAPH-",
                change_submits=True,  # mouse click events
                background_color='lightblue',
                drag_submits=True),
            sg.Graph(
                canvas_size=(cap.shape[1], cap.shape[0]),
                graph_bottom_left=(0,cap.shape[0]),
                graph_top_right=(cap.shape[1], 0),
                key="-OUT-",
                change_submits=False,  # mouse click events
                background_color='lightblue',
                drag_submits=False),
        ],
        [
            sg.Text(key='info', size=(60, 1)),
            sg.Button('Save (Fullsize)')
        ],
    ]

window = sg.Window("IPM Mapping", layout, finalize=True)
# get the graph element for ease of use later
graph = window["-GRAPH-"]  # type: sg.Graph
out_graph = window["-OUT-"]
graph.draw_image(data=image_file, location=(0,0)) if image_file else None
for i in range(len(points)):
    graph.draw_circle(points[i+2],radius=6,line_color='blue',line_width=3,fill_color='blue')
priors = draw_poly(graph,points)
dragging = false_drag = False
start_point = end_point  = None
fig = None
ipm_img = None

while True:
    event, values = window.read()

    if event == sg.WIN_CLOSED:
        break  # exit

    if event == 'Save (Fullsize)':
        save_scaled_cap_as_file(orig_cap,points,cap.shape[1],cap.shape[0])
    if event == "-GRAPH-":  # if there's a "Graph" event, then it's a mouse
        x, y = values["-GRAPH-"]
        #prevent loss of focus by quick mouse moves
        if not fig:
            fig = get_drag_fig(graph,points,x,y)
        if not dragging and not fig:
            false_drag = True
            #user is moving mouse without having clicked a circle
        if fig and not false_drag:
            if not dragging:
                start_point = (x, y)
                dragging = True
                lastxy = x, y
                delta_x, delta_y = lastxy[0]-points[fig][0] ,lastxy[1] -  points[fig][1]
                graph.move_figure(fig, delta_x, delta_y)
                points[fig] = (x,y)
                if ipm_img:
                    out_graph.delete_figure(ipm_img)
            else:
                
                if x>cap.shape[1]:
                    x = cap.shape[1] - 1

                if y>cap.shape[0]:
                    y = cap.shape[0] - 1
                end_point = (x, y)

            delta_x, delta_y = x - lastxy[0], y - lastxy[1]
            lastxy = x,y
            
            if end_point:
                graph.move_figure(fig, delta_x, delta_y)

                points[fig] = (x,y)
                if priors:
                    for prior in priors:
                        graph.delete_figure(prior)
                priors = draw_poly(graph,points)
                print(points)
                if ipm_img:
                    out_graph.delete_figure(ipm_img)
                out = apply_ipm(cap,points)
                out_img=cv2.imencode('.png', out)[1].tobytes()
                ipm_img = out_graph.draw_image(data=out_img, location=(0,0))
                out_graph.update()
                graph.update()

    elif event.endswith('+UP') and fig:  # The drawing has ended because mouse up
        window["info"].update(value=f"grabbed object from {start_point} to {end_point}")

        out = apply_ipm(cap,points)
        out_img=cv2.imencode('.png', out)[1].tobytes()
        start_point, end_point = None, None  # enable grabbing a new rect
        dragging  = False
        false_drag = False
        fig = None

    else:
        false_drag = False
        print("unhandled event", event, values)