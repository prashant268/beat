import logging
import json

# Azure Functions
import azure.functions as func

# Other Helper Libraries
from math import radians, cos, sin, asin, sqrt
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    # Get Method for Sanity Check
    if req.method == 'GET':
        message = {
            'message': 'This HTTP triggered function executed successfully.',
            'statuscode': 200
        }
        return func.HttpResponse(
            json.dumps(message),
            mimetype="application/json",
            status_code=200
        )

    # Parsing Arguments
    dataparser = {}
    try:
        req_body = req.get_json()
    except ValueError:
        message = {
            'message': 'Invalid JSON Body',
            'statuscode': 400
        }
        return func.HttpResponse(
            json.dumps(message),
            mimetype="application/json",
            status_code=400
        )
    else:
        dataparser['city'] = req_body.get('city')
        if not dataparser['city']:
            message = {
                'message': helpermessage1('city'),
                'statuscode': 400
            }
            return func.HttpResponse(
                json.dumps(message),
                mimetype="application/json",
                status_code=400
            )

        dataparser['source'] = req_body.get('source')
        if not dataparser['source']:
            message = {
                'message': helpermessage1('source'),
                'statuscode': 400
            }
            return func.HttpResponse(
                json.dumps(message),
                mimetype="application/json",
                status_code=400
            )

        dataparser['customers'] = req_body.get('customers')
        if not dataparser['customers']:
            message = {
                'message': helpermessage1('customers'),
                'statuscode': 400
            }
            return func.HttpResponse(
                json.dumps(message),
                mimetype="application/json",
                status_code=400
            )

    # Format Arguments for TSP
    algodata = {}
    algodata['routename'] = []
    algodata['coordinates'] = []
    algodata['id'] = []

    # Parse Source
    if 'name' in dataparser['source']:
        algodata['routename'].append(
            dataparser['source']['name']
        )
    else:
        message = {
            'message': helpermessage2('Source Name'),
            'statuscode': 400
        }
        return func.HttpResponse(
            json.dumps(message),
            mimetype="application/json",
            status_code=400
        )
    if 'id' in dataparser['source']:
        algodata['id'].append(
            dataparser['source']['id']
        )
    else:
        message = {
            'message': helpermessage2('Source Id'),
            'statuscode': 400
        }
        return func.HttpResponse(
            json.dumps(message),
            mimetype="application/json",
            status_code=400
        )
    if 'customerLocation' in dataparser['source']:
        if 'coordinates' in dataparser['source']['customerLocation']:
            algodata['coordinates'].append(
                tuple(
                        dataparser['source']['customerLocation'][
                            'coordinates'
                        ]
                    )
            )
        else:
            message = {
                'message': helpermessage2('Source coordinates'),
                'statuscode': 400
            }
            return func.HttpResponse(
                json.dumps(message),
                mimetype="application/json",
                status_code=400
            )
    else:
        message = {
            'message': helpermessage2('Source customerLocation'),
            'statuscode': 400
        }
        return func.HttpResponse(
            json.dumps(message),
            mimetype="application/json",
            status_code=400
        )

    # Parse Customers
    skipdata = []
    for customer in dataparser['customers']:
        if 'customerName' in customer and 'customerId' in customer and 'customerLocation' in customer and 'coordinates' in customer['customerLocation']:
            if len(customer['customerLocation']['coordinates']) == 2:
                algodata['routename'].append(
                    customer['customerName']
                )
                algodata['id'].append(
                    customer['customerId']
                )
                algodata['coordinates'].append(
                    tuple(
                            customer['customerLocation']['coordinates']
                        )
                )
            else:
                skipdata.append(customer)
        else:
            skipdata.append(customer)

    # TSP Format Model Data
    algodata = create_data_model(algodata)

    # TSP Run Algorithm
    try:
        temp = travellingsalesman(algodata)
    except Exception as e:
        logging.error(e)
        message = {
                'message': 'Algorithm did not converge.',
                'statuscode': 200
        }
        return func.HttpResponse(
            json.dumps(message),
            mimetype="application/json",
            status_code=200
        )

    if type(temp) is not dict:
        message = {
            'message': temp,
            'statuscode': 200
        }
        return func.HttpResponse(
            json.dumps(message),
            mimetype="application/json",
            status_code=200
        )

    # TSP Format Return Data
    temp['id'] = temp['id'][1:-1]
    temp['routename'] = temp['routename'][1:-1]
    temp['coordinates'] = temp['coordinates'][1:-1]
    returndata = {}
    returndata['customers'] = []
    for index in range(len(temp['id'])):
        _ = {}
        _['customerName'] = temp['routename'][index]
        _['customerId'] = temp['id'][index]
        _['customerLocation'] = {
            "type": "Point",
            "coordinates": list(temp['coordinates'][index])
        }
        _['seq'] = index + 1
        returndata['customers'].append(_)
    returndata['skipcustomers'] = skipdata

    return func.HttpResponse(
        json.dumps(returndata),
        mimetype="application/json",
        status_code=200
    )


def helpermessage1(category):
    return f"This HTTP triggered function executed successfully. Pass a {category} in the request body."


def helpermessage2(category):
    return f"This HTTP triggered function executed successfully. {category} does not exist."


def create_data_model(algodata):
    """Stores the data for the problem."""
    data = {}
    # Locations in block units
    data['routename'] = algodata['routename']
    data['coordinates'] = algodata['coordinates']
    data['id'] = algodata['id']
    data['num_vehicles'] = 1
    data['depot'] = 0
    return data


def compute_distance_matrix(locations):
    """Creates callback to return distance between points."""
    distances = {}
    for from_counter, from_node in enumerate(locations):
        distances[from_counter] = {}
        for to_counter, to_node in enumerate(locations):
            if from_counter == to_counter:
                distances[from_counter][to_counter] = 0
            else:
                # Haversine distance
                lon1, lat1, lon2, lat2 = map(
                    radians,
                    [
                        from_node[0], from_node[1],
                        to_node[0], to_node[1]
                    ]
                )
                dlon = lon2 - lon1
                dlat = lat2 - lat1
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                c = 2 * asin(sqrt(a))
                r = 6371
                distances[from_counter][to_counter] = (c * r)
    return distances


def return_solution(data, manager, routing, solution):
    """Solution on console."""
    returndata = {}
    returndata['id'] = []
    returndata['routename'] = []
    returndata['coordinates'] = []
    index = routing.Start(0)
    route_distance = 0
    while not routing.IsEnd(index):
        returndata['id'].append(
            data['id'][manager.IndexToNode(index)]
        )
        returndata['routename'].append(
            data['routename'][manager.IndexToNode(index)]
        )
        returndata['coordinates'].append(
            data['coordinates'][manager.IndexToNode(index)]
        )
        previous_index = index
        index = solution.Value(routing.NextVar(index))
        route_distance += routing.GetArcCostForVehicle(
            previous_index,
            index,
            0
        )
    returndata['id'].append(
        data['id'][manager.IndexToNode(index)]
    )
    returndata['routename'].append(
        data['routename'][manager.IndexToNode(index)]
    )
    returndata['coordinates'].append(
        data['coordinates'][manager.IndexToNode(index)]
    )
    return returndata


def travellingsalesman(data):
    """Entry point of the program."""

    # Create the routing index manager.
    manager = pywrapcp.RoutingIndexManager(len(data['coordinates']),
                                           data['num_vehicles'], data['depot'])

    # Create Routing Model.
    routing = pywrapcp.RoutingModel(manager)

    distance_matrix = compute_distance_matrix(data['coordinates'])

    def distance_callback(from_index, to_index):
        """Returns the distance between the two nodes."""
        # Convert from routing variable Index to distance matrix NodeIndex.
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)

    # Define cost of each arc.
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Setting first solution heuristic.
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    search_parameters.local_search_metaheuristic = (
           routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
        search_parameters.time_limit.FromSeconds(10)

    # Solve the problem.
    solution = routing.SolveWithParameters(search_parameters)

    # Print solution on console.
    if solution:
        return return_solution(data, manager, routing, solution)
    else:
        return "No available solution"
