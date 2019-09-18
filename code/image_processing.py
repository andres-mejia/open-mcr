import math
import typing
from pathlib import Path, PurePath

import cv2
import numpy as np


def convert_to_grayscale(image: np.array) -> np.array:
  """Convert an image to grayscale."""
  return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def remove_hf_noise(image: np.array) -> np.array:
  """Blur image slightly to remove high-frequency noise."""
  return cv2.GaussianBlur(image, (3, 3), 0)


def detect_edges(image: np.array) -> np.array:
  """Detect edges in the image."""
  low_threshold = 100
  return cv2.Canny(image, low_threshold, low_threshold * 3, edges=3)


def find_contours(edges: np.array):
  """Find the contours in an edge-detected image."""
  contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
  return contours


def approx_poly(contour):
  """Approximate the simple polygon for the contour."""
  perimeter = cv2.arcLength(contour, True)
  return cv2.approxPolyDP(contour, 0.02 * perimeter, True)


def calc_2d_dist(point_a, point_b):
  """Calculate the Euclidean distance between two 2d points."""
  return ((point_a[0] - point_b[0])**2 + (point_a[1] - point_b[1])**2)**0.5


def calc_angle(end_a, shared, end_b):
  """Calculate the internal angle between the two vectors (always in 0-180 range)."""
  mag_a = calc_2d_dist(shared, end_a)
  mag_b = calc_2d_dist(shared, end_b)
  dist_ab = calc_2d_dist(end_a, end_b)
  cosine = (mag_a**2 + mag_b**2 - dist_ab**2) / (2 * mag_a * mag_b)
  angle = abs(math.acos(cosine))
  return angle if angle <= 180 else angle - 180


def calc_corner_angles(contour):
  """For a list of points, returns a list of numbers, where each element with
  index `i` is the angle between points `i-1`, `i`, and `i+1`."""
  result = []
  for i, point in enumerate(contour):
    previous_point = contour[i - 1]
    next_point = contour[i + 1] if (i + 1 < len(contour)) else contour[0]
    result.append(calc_angle(previous_point, point, next_point))
  return result


def calc_side_lengths(contour):
  """For a list of points, returns a list of numbers, where each element with
  index `i` is the distance from point `i` to point `i+1`."""
  result = []
  for i, point in enumerate(contour):
    next_point = contour[i + 1] if (i + 1 < len(contour)) else contour[0]
    result.append(calc_2d_dist(point, next_point))
  return result


def is_approx_equal(value_a: typing.Union[int, float],
                    value_b: typing.Union[int, float],
                    tolerance: float = 0.1) -> bool:
  """Returns true if the difference of `a` and `b` is within tolerance of the smaller."""
  return abs(value_a - value_b) <= (tolerance * min(value_a, value_b))


def all_approx_equal(values: typing.List[typing.Union[int, float]], target: typing.Union[int, float, None] = None, tolerance: float = 0.1):
  """Returns `True` if every element in `values` is within `tolerance` of `target`.
  
  Args:
    values: List of numeric values to check for equality.
    target: Target value. If not provided, uses the mean to check if all list
      are approximately equal to themselves.
    tolerance: The tolerance for equality. 0.1 is 10% of the smaller value.
  """
  target_ = target if target is not None else mean(values)
  return all([is_approx_equal(value, target_, tolerance) for value in values])


def get_image(path: PurePath) -> np.array:
  """Returns the cv2 image located at the given path."""
  return cv2.imread(str(path))


def find_polygons(image: np.array):
  """Returns a list of polygons found in the image."""
  processed_image = remove_hf_noise(convert_to_grayscale(image))
  edges = detect_edges(processed_image)
  all_contours = find_contours(edges)
  polygons = [approx_poly(contour) for contour in all_contours]
  return polygons


def find_greatest_two(numbers: typing.List[float]):
  """Find the indices of the greatest two numbers in the list.

  Returns:
    A tuple where the first element is the index of the greatest item and the 
    second element is the index of the second-greatest item.
  """
  # ((longest length, longest index), (2nd longest length, 2nd longest index))
  greatest = [[-1, -1], [-1, -1]]
  for i, value in enumerate(numbers):
    if value > greatest[0][0]:
      greatest[1][0] = greatest[0][0]
      greatest[1][1] = greatest[0][1]
      greatest[0][0] = value
      greatest[0][1] = i
    elif value > greatest[1][0]:
      greatest[1][0] = value
      greatest[1][1] = i
  return (greatest[0][1], greatest[1][1])


def is_adjacent_indices(index_a, index_b, items):
  """Check that the given indices are next to each other or are the first and
  last indices in the list. Order of a and b do not matter."""
  return ((index_a == 0 and index_b == len(items) - 1)
          or (index_b == 0 and index_a == len(items) - 1)
          or abs(index_a - index_b) == 1)


def all_approx_square(contour):
  """Returns true if every angle in `contour` is approximately right (90deg)."""
  angles = calc_corner_angles(contour)
  return all_approx_equal(angles, math.pi / 2)


def unnest(nested):
  """Flatten a list in the form `[[[a,b]], [[c,d]], [[e,f]]]` to `[[a,b], [c,d], [e,f]]`."""
  return [e[0] for e in nested]


def mean(values):
  """Returns the average of the list of numeric values."""
  return sum(values) / len(values)

def divide_some(values, indices, divisor):
  """Returns a copy of `values` where items at `indices` are divided by `divisor`."""
  return [x if i not in indices else x / divisor for x, i in enumerate(values)]


def find_top_left_corner_mark(unflat_contours):
  """Given a list of contours, find the top left corner mark."""
  # Perform this search in one loop to maintain O(N) complexity.
  # For speed, perform fastest calculations first to call `continue` asap.
  for contour in unflat_contours:
    if len(contour) != 6:
      continue

    flat_contour = unnest(contour)
    if not all_approx_square(flat_contour):
      continue

    side_lengths = calc_side_lengths(flat_contour)
    longest_sides_indices = find_greatest_two(side_lengths)

    if not is_adjacent_indices(*longest_sides_indices, side_lengths):
      continue

    # The longest sides should be about twice the length of the other sides
    unit_lengths = divide_some(side_lengths, longest_sides_indices, 2)
    if not all_approx_equal(unit_lengths):
      continue

    # Returns the first viable polygon found
    # TODO: Consider all found polygons and choose the most likely
    return contour


def get_dimensions(image: np.array) -> typing.Tuple[int, int]:
  """Returns the dimensions of the image in `(width, height)` form."""
  height, width, _ = image.shape
  return width, height


def find_squares(unflat_contours):
  """Given a list of contours, return the ones which are squares."""
  squares = []
  for contour in unflat_contours:
    if len(contour) != 4:
      continue

    flat_contour = unnest(contour)

    side_lengths = calc_side_lengths(flat_contour)
    if not all_approx_equal(side_lengths):
      continue

    angles = calc_corner_angles(flat_contour)
    if not all_approx_square(angles):
      continue

    squares.append(contour)
  return squares


sample_img_location = Path(
    __file__).parent.parent / "examples" / "left_corner_marks" / "11.png"
sample_image = get_image(sample_img_location)
all_polygons = find_polygons(sample_image)
top_left_mark = find_top_left_corner_mark(all_polygons)
red = (0, 0, 255)
cv2.drawContours(sample_image, [top_left_mark], -1, red, 1)
all_squares = find_squares(all_polygons)
blue = (255, 0, 0)
cv2.drawContours(sample_image, all_squares, -1, blue, 1)
cv2.imshow("image", sample_image)
cv2.waitKey(0)
