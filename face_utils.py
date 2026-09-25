import cv2
import os
import face_recognition
import pickle
from datetime import datetime

from database import get_connection


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASET_DIR = os.path.join(BASE_DIR, "dataset")
ENCODING_DIR = os.path.join(BASE_DIR, "encodings")
ENCODING_FILE = os.path.join(ENCODING_DIR, "encodings.pkl")


# Create required folders
os.makedirs(DATASET_DIR, exist_ok=True)
os.makedirs(ENCODING_DIR, exist_ok=True)


# ============================================================
# 1. CAPTURE FACE IMAGES
# ============================================================

def capture_faces(student_id, number_of_images=10):

    student_folder = os.path.join(
        DATASET_DIR,
        str(student_id)
    )

    os.makedirs(student_folder, exist_ok=True)

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("ERROR: Camera could not be opened.")
        return False

    count = 0

    print()
    print("=" * 50)
    print("FACE CAPTURE STARTED")
    print("=" * 50)
    print("Press C = Capture Image")
    print("Press Q = Quit")
    print("=" * 50)

    while True:

        ret, frame = camera.read()

        if not ret:
            print("ERROR: Could not read camera.")
            break

        cv2.imshow(
            "Capture Face - Press C to Capture / Q to Quit",
            frame
        )

        key = cv2.waitKey(1) & 0xFF

        # Capture image
        if key == ord("c"):

            filename = os.path.join(
                student_folder,
                f"image_{count + 1}.jpg"
            )

            if cv2.imwrite(filename, frame):

                count += 1

                print(
                    f"Image {count}/{number_of_images} saved"
                )

            else:

                print("ERROR: Image could not be saved.")

            if count >= number_of_images:

                print()
                print("Face images captured successfully.")

                break

        # Quit
        elif key == ord("q"):

            print("Face capture stopped.")
            break

    camera.release()
    cv2.destroyAllWindows()

    return count > 0


# ============================================================
# 2. CREATE FACE ENCODINGS
# ============================================================

def create_encodings():

    known_encodings = []
    known_ids = []

    os.makedirs(DATASET_DIR, exist_ok=True)
    os.makedirs(ENCODING_DIR, exist_ok=True)

    print()
    print("=" * 50)
    print("CREATING FACE ENCODINGS")
    print("=" * 50)

    if not os.path.exists(DATASET_DIR):

        print("ERROR: Dataset folder not found.")
        return False

    # Go through student folders
    for student_id in os.listdir(DATASET_DIR):

        student_folder = os.path.join(
            DATASET_DIR,
            student_id
        )

        if not os.path.isdir(student_folder):
            continue

        # Student folder name must be an integer
        try:

            numeric_student_id = int(student_id)

        except ValueError:

            print(
                f"Skipping invalid folder: {student_id}"
            )

            continue

        # Go through images
        for image_name in os.listdir(student_folder):

            image_path = os.path.join(
                student_folder,
                image_name
            )

            if not image_name.lower().endswith(
                (".jpg", ".jpeg", ".png")
            ):
                continue

            try:

                # Load image
                image = face_recognition.load_image_file(
                    image_path
                )

                # Find face
                locations = face_recognition.face_locations(
                    image
                )

                # Exactly one face required
                if len(locations) != 1:

                    print(
                        f"Skipped: {image_name} "
                        f"(faces found: {len(locations)})"
                    )

                    continue

                # Create encoding
                encodings = face_recognition.face_encodings(
                    image,
                    locations
                )

                if len(encodings) == 0:

                    print(
                        f"Skipped: No encoding for {image_name}"
                    )

                    continue

                known_encodings.append(
                    encodings[0]
                )

                known_ids.append(
                    numeric_student_id
                )

                print(
                    f"Encoded: Student {numeric_student_id} "
                    f"- {image_name}"
                )

            except Exception as e:

                print(
                    f"Error processing {image_name}: {e}"
                )

    # No valid faces
    if len(known_encodings) == 0:

        print()
        print("ERROR: No valid face encodings created.")
        print("Please capture face images again.")

        return False

    # Save encoding file
    with open(
        ENCODING_FILE,
        "wb"
    ) as file:

        pickle.dump(
            {
                "encodings": known_encodings,
                "ids": known_ids
            },
            file
        )

    print()
    print("=" * 50)
    print("FACE ENCODINGS CREATED SUCCESSFULLY")
    print(
        "Total face encodings:",
        len(known_encodings)
    )
    print("=" * 50)

    return True


# ============================================================
# 3. MARK ATTENDANCE
# ============================================================
def mark_attendance():

    # Check encoding file
    if not os.path.exists(ENCODING_FILE):

        print("ERROR: Encoding file not found.")
        print("Please register a student first.")

        return False

    # Load encodings
    try:

        with open(
            ENCODING_FILE,
            "rb"
        ) as file:

            data = pickle.load(file)

    except Exception as e:

        print(
            f"ERROR: Could not load encoding file: {e}"
        )

        return False

    known_encodings = data.get(
        "encodings",
        []
    )

    known_ids = data.get(
        "ids",
        []
    )

    if not known_encodings:

        print("ERROR: No face encodings available.")
        return False

    if len(known_encodings) != len(known_ids):

        print("ERROR: Encoding data is invalid.")
        return False

    # Open camera
    camera = cv2.VideoCapture(0)

    if not camera.isOpened():

        print("ERROR: Camera could not be opened.")
        return False

    print()
    print("=" * 50)
    print("ATTENDANCE SYSTEM STARTED")
    print("=" * 50)
    print("Show your face to the camera.")
    print("Press Q to stop.")
    print("=" * 50)

    recognized = False

    while True:

        ret, frame = camera.read()

        if not ret:

            print("ERROR: Could not read camera.")
            break

        # Resize for faster recognition
        small_frame = cv2.resize(
            frame,
            (0, 0),
            fx=0.25,
            fy=0.25
        )

        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(
            small_frame,
            cv2.COLOR_BGR2RGB
        )

        # Detect faces
        face_locations = face_recognition.face_locations(
            rgb_frame
        )

        # Create encodings
        face_encodings = face_recognition.face_encodings(
            rgb_frame,
            face_locations
        )

        # Check every detected face
        for face_encoding, face_location in zip(
            face_encodings,
            face_locations
        ):

            # Compare face
            matches = face_recognition.compare_faces(
                known_encodings,
                face_encoding,
                tolerance=0.50
            )

            # Face distance
            face_distances = face_recognition.face_distance(
                known_encodings,
                face_encoding
            )

            if len(face_distances) == 0:
                continue

            # Best match
            best_match_index = face_distances.argmin()

            # =================================================
            # RECOGNIZED FACE
            # =================================================

            if matches[best_match_index]:

                student_id = known_ids[
                    best_match_index
                ]

                conn = get_connection()

                try:

                    # Get student
                    student = conn.execute(
                        """
                        SELECT *
                        FROM students
                        WHERE id = ?
                        """,
                        (student_id,)
                    ).fetchone()

                    if student is None:

                        print(
                            f"Student ID {student_id} "
                            f"not found."
                        )

                        continue

                    # Current date
                    today = datetime.now().strftime(
                        "%Y-%m-%d"
                    )

                    # Current time
                    current_time = datetime.now().strftime(
                        "%H:%M:%S"
                    )

                    # Check today's attendance
                    existing = conn.execute(
                        """
                        SELECT id
                        FROM attendance
                        WHERE student_id = ?
                        AND date = ?
                        """,
                        (
                            student_id,
                            today
                        )
                    ).fetchone()

                    # Already marked
                    if existing:

                        print()
                        print(
                            f"Attendance already marked: "
                            f"{student['name']}"
                        )

                    # Mark attendance
                    else:

                        conn.execute(
                            """
                            INSERT INTO attendance
                            (
                                student_id,
                                date,
                                time
                            )
                            VALUES (?, ?, ?)
                            """,
                            (
                                student_id,
                                today,
                                current_time
                            )
                        )

                        conn.commit()

                        print()
                        print("=" * 50)
                        print("ATTENDANCE MARKED SUCCESSFULLY")
                        print("=" * 50)
                        print(
                            f"Name: {student['name']}"
                        )
                        print(
                            f"Roll No: {student['roll_no']}"
                        )
                        print(
                            f"Date: {today}"
                        )
                        print(
                            f"Time: {current_time}"
                        )
                        print("=" * 50)

                    recognized = True

                    # Draw green rectangle
                    top, right, bottom, left = face_location

                    top *= 4
                    right *= 4
                    bottom *= 4
                    left *= 4

                    cv2.rectangle(
                        frame,
                        (left, top),
                        (right, bottom),
                        (0, 255, 0),
                        2
                    )

                    cv2.putText(
                        frame,
                        student["name"],
                        (left, top - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 0),
                        2
                    )

                except Exception as e:

                    print(
                        f"Attendance database error: {e}"
                    )

                finally:

                    conn.close()

            # =================================================
            # UNKNOWN FACE
            # =================================================

            else:

                top, right, bottom, left = face_location

                top *= 4
                right *= 4
                bottom *= 4
                left *= 4

                cv2.rectangle(
                    frame,
                    (left, top),
                    (right, bottom),
                    (0, 0, 255),
                    2
                )

                cv2.putText(
                    frame,
                    "Unknown",
                    (left, top - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2
                )

        # Show camera
        cv2.imshow(
            "Face Recognition Attendance - Press Q to Exit",
            frame
        )

        key = cv2.waitKey(1) & 0xFF

        # Quit
        if key == ord("q"):

            break

        # Stop after recognition
        if recognized:

            cv2.waitKey(1500)

            break

    # Release camera
    camera.release()
    cv2.destroyAllWindows()

    return recognized