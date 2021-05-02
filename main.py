import PySimpleGUI as sg
import cv2
import numpy as np
from PIL import ImageGrab
"""
    PySimpleGUI self-learning exercise for combination with OpenCV and UI updates.
    A perspective mapping tool used to visualise how inverse perspective mapping takes place through a realtime output corresponding to input movement.
    Could also be used as a quick 'CamScan' type tool as required - output images are returned at full resolution unliked scaled UI output however it has
    not been tested robustly so better off as a demo application.

    Heavily inspired and based off the DragRect Demo - this example program showcases the simplicity of extension and overall awesomeness of PySimpleGUI
    https://github.com/PySimpleGUI/PySimpleGUI/blob/master/DemoPrograms/Demo_Graph_Drag_Rectangle.py 

    Perspective Mapping inspired from PyImageSearch
    https://www.pyimagesearch.com/2014/05/05/building-pokedex-python-opencv-perspective-warping-step-5-6/
"""
def get_drag_fig(graph,points,x,y):
    drag_figures = graph.get_figures_at_location((x,y))

    #we only want to drag one at a time - return first encountered
    for fig in drag_figures:
        if fig in points.keys():
            return fig

    return False
        
def draw_poly(graph,points):
    priors = []
    lpoints = list(points.values())

    #Draw lines between each corner to form an enclosed polygon
    for i in range(len(lpoints)-1):
        priors.append(graph.draw_line(lpoints[i],lpoints[i+1],color='red'))
    priors.append(graph.draw_line(lpoints[0],lpoints[-1],color='red'))

    return priors

def translate_corner(graph,fig,end_point):
    #Calculate delta and move the fig in question
    graph.move_figure(fig, end_point[0]-points[fig][0] ,end_point[1] -  points[fig][1])
    #Update variable tracking corner positions
    points[fig] = (x,y)

def apply_ipm(cap, points):
    #This portion was directly inspired from https://www.pyimagesearch.com/2014/05/05/building-pokedex-python-opencv-perspective-warping-step-5-6/
    #Dr. Rosebrock always has the best explanations of exactly what his code does.

    #Convert our points dict/list to a numpy array
    #NOTE: probably fine to leave dtype as int but keep consistent with dst for now
    if type(points) == dict:
        src = np.array([list(y) for y in points.values()],dtype='float32')
    else:
        src = np.array([list(y) for y in points],dtype='float32')

    (tl, tr, br, bl) = src

    #NOTE using trig transforms would be more efficient than below. But it's fast enough and very readable
    #Calculate euclidean width
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))

    #Calculate euclidean height
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))

    #Take max width and height to define output shape - important to maintain aspect ratio
    maxWidth = max(int(widthA), int(widthB))
    maxHeight = max(int(heightA), int(heightB))
    #
    dst =  np.array([
            [0, 0], #TL
            [maxWidth, 0], #TR
            [maxWidth, maxHeight], #BR
            [0, maxHeight]], #BL 
            dtype = "float32")

    #Get perspective mapping between src and dst
    persT = cv2.getPerspectiveTransform(src, dst)

    #Conduct the mat transformation to turn src into dst
    return cv2.warpPerspective(cap, persT, (maxWidth, maxHeight))

def draw_output(output_graph,cap,points):
    out = apply_ipm(cap,points)
    out_img=cv2.imencode('.png', out)[1].tobytes()
    return out_graph.draw_image(data=out_img, location=(0,0))

def save_scaled_cap_as_file(fname, orig_cap,points,scaled_width,scaled_height):
    #Conduct the perspective transform as per output graph but instead use unscaled inputs as applicable
    #to generate a full resolution output
    orig_h,orig_w,_ = orig_cap.shape
    points = [(x[0]*orig_w/scaled_width,x[1]*orig_h/scaled_height)  for x in points.values()]
    out_cap = apply_ipm(orig_cap,points)
    cv2.imwrite(f'{fname}.png',out_cap)


# Get the folder containing the images from the user
fp = sg.popup_get_file('Image file to open', default_path='')
if not fp:
    sg.popup_cancel('Cancelling')
    raise SystemExit()

#Read in desired image
try:
    orig_cap = cap = cv2.imread(fp)
except Exception as e :
    sg.popup_cancel(f'Image could not be opened. Full error: {e}')
    raise SystemExit() 

#Ensure a max size scaled such that graphs/canvas' comfortably fit on page
max_size = 600 
if any(x > max_size for x in cap.shape):
    rscl_fctr_y = cap.shape[0]//max_size
    rscl_fctr_x = cap.shape[1]//max_size
    orig_cap = cap
    cap = cv2.resize(cap,dsize=(cap.shape[0]//rscl_fctr_y,cap.shape[1]//rscl_fctr_x))

#Encode static background for input graph
image_file=cv2.imencode('.png', cap)[1].tobytes()

#Track 4 points of document
#Points are intentionally non-sequential to match OPENCV warp ordering to be tl tr br bl
#not necessary but makes subsequent transform easier
points = {2:(20,20),
            5:(cap.shape[0]//2,20),
            3:(cap.shape[0]//2,cap.shape[1]//2),
            4:(20,cap.shape[1]//2),
        }

#Declare and initiate layout + window
layout = [
        [
            sg.Graph(
                canvas_size=(cap.shape[1], cap.shape[0]),
                graph_bottom_left=(0,cap.shape[0]),
                graph_top_right=(cap.shape[1], 0),
                key="-GRAPH-",
                change_submits=True, 
                background_color='lightblue',
                drag_submits=True),
            sg.Graph(
                canvas_size=(cap.shape[1], cap.shape[0]),
                graph_bottom_left=(0,cap.shape[0]),
                graph_top_right=(cap.shape[1], 0),
                key="-OUT-",
                change_submits=False,  
                background_color='lightblue',
                drag_submits=False),
        ],
        [
            sg.Text(key='info', size=(60, 1)),
            sg.Text('Filename: ', size=(15, 1)), 
            sg.InputText(key="-FNAME-",default_text='example_name'),
            sg.Button('Save PNG (Fullsize)')
        ],
    ]

window = sg.Window("IPM Mapping", layout, finalize=True)

# Save handles to input and output graph elements 
graph = window["-GRAPH-"]  # type: sg.Graph
out_graph = window["-OUT-"]

#Initiate the input graph workspace
graph.draw_image(data=image_file, location=(0,0)) if image_file else None
for i in range(len(points)):
    graph.draw_circle(points[i+2],radius=6,line_color='blue',line_width=3,fill_color='blue')
priors = draw_poly(graph,points)

#Draw initial output
ipm_img = draw_output(out_graph,cap,points)

#Setup 
dragging = false_drag = False
start_point = end_point  = None
fig = None


while True:
    event, values = window.read()

    if event == sg.WIN_CLOSED:
        break  # exit
    
    #Save output image - TODO debounce save button?
    if event == 'Save PNG (Fullsize)':
        window["info"].update(value=f"Saving Image...")
        fname = values['-FNAME-']
        save_scaled_cap_as_file(fname,orig_cap,points,cap.shape[1],cap.shape[0])
        window["info"].update(value=f"Save Successful! : {fname}.png")

    #Graph event on input 
    if event == "-GRAPH-": 
        x, y = values["-GRAPH-"]
        #prevent loss of focus/dropped corner issue by quick mouse moves by only getting a new fig when there is not currently one being dragged
        if not fig:
            fig = get_drag_fig(graph,points,x,y)
        
        #User is dragging mouse without a valid corner - set false_drag to prevent subsequent elements being picked up
        if not dragging and not fig:
            false_drag = True
            #user is moving mouse without having clicked a circle

        #Valid corner movement
        if fig and not false_drag:

            if not dragging:
                start_point = (x, y)
                dragging = True

                #Corner circles can be grabbed anywhere within their radius. Prevent tracked points becoming desynced by immediately moving the 
                #circle's center to the cursor position
                translate_corner(graph,fig,(x,y))

                #Delete remnant output from previous mouse release
                if ipm_img:
                    out_graph.delete_figure(ipm_img)
            else:
                #Ensure corners cannot leave graph
                if x>cap.shape[1]:
                    x = cap.shape[1] - 1
                if x<0:
                    x = 1
                if y>cap.shape[0]:
                    y = cap.shape[0] - 1
                if y<0:
                    y = 1
                end_point = (x, y)


            if end_point:
                #Translate corner to new mouse position
                translate_corner(graph,fig,(x,y))

                #Delete red contours and redraw
                if priors:
                    for prior in priors:
                        graph.delete_figure(prior)
                priors = draw_poly(graph,points)
                print(points)

                #Delete previous output image and remake based on new points
                if ipm_img:
                    out_graph.delete_figure(ipm_img)

                ipm_img = draw_output(out_graph,cap,points)

                #Update output and input
                out_graph.update()
                graph.update()

    elif event.endswith('+UP') and fig:  # The movement has ended because mouse up
        window["info"].update(value=f"Moved corner {fig} from {start_point} to {end_point}")

        #Reset all movement tracking variables
        start_point, end_point = None, None 
        dragging  = False
        false_drag = False
        fig = None

    else:
        #Handle the end of false drags 
        false_drag = False
        
