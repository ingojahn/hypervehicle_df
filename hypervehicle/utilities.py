import os
import sys
import glob
import time
import numpy as np
import pandas as pd
from stl import mesh
import xml.etree.ElementTree as ET


def parametricSurfce2stl(
    parametric_surface,
    triangles_per_edge,
    mirror_y=False,
    re_evaluate_centroid=False,
    flip_faces=False,
):
    """
    Function to convert parametric_surface generated using the Eilmer Geometry
    Package into a stl mesh object.

    Inputs:
        parametric_surface - surface object
        triangles_per_edge - resolution for stl object.
        mirror_y - create mirror image about x-z plane
    Outputs:
        stl_mesh - triangulated mesh object suitable for numpy-stl
    """
    if triangles_per_edge is None:
        raise Exception(
            "Please define STL resolution, either component-wise, or for "
            + "the entire vehicle."
        )

    # create list of vertices
    r_list = np.linspace(0.0, 1.0, triangles_per_edge + 1)
    s_list = np.linspace(0.0, 1.0, triangles_per_edge + 1)

    y_mult = -1 if mirror_y else 1
    index = (triangles_per_edge + 1) ** 2

    # create vertices for corner points of each quad cell
    vertices = np.empty(((triangles_per_edge + 1) ** 2 + triangles_per_edge**2, 3))
    for i, r in enumerate(r_list):
        for j, s in enumerate(s_list):
            p1 = time.time()
            pos = parametric_surface(r, s)

            vertices[j * (triangles_per_edge + 1) + i] = np.array(
                [pos.x, y_mult * pos.y, pos.z]
            )

            # create vertices for centre point of each quad cell,
            # which is used to split each cell into 4x triangles
            try:
                if re_evaluate_centroid is True:
                    r = 0.5 * (r_list[i] + r_list[i + 1])
                    r = 0.5 * (s_list[i] + s_list[i + 1])
                    pos = parametric_surface(r, s)
                    pos_x = pos.x
                    pos_y = pos.y
                    pos_z = pos.z

                else:
                    r0 = r_list[i]
                    r1 = r_list[i + 1]
                    s0 = s_list[j]
                    s1 = s_list[j + 1]

                    pos00 = parametric_surface(r0, s0)
                    pos10 = parametric_surface(r1, s0)
                    pos01 = parametric_surface(r0, s1)
                    pos11 = parametric_surface(r1, s1)

                    pos_x = 0.25 * (pos00.x + pos10.x + pos01.x + pos11.x)
                    pos_y = 0.25 * (pos00.y + pos10.y + pos01.y + pos11.y)
                    pos_z = 0.25 * (pos00.z + pos10.z + pos01.z + pos11.z)

                vertices[index + (j * triangles_per_edge + i)] = np.array(
                    [
                        pos_x,
                        y_mult * pos_y,
                        pos_z,
                    ]
                )
            except:
                pass

    # Create list of faces
    faces = []  # np.zeros((triangles_per_edge**2*4, 3))
    for i in range(triangles_per_edge):
        for j in range(triangles_per_edge):
            p00 = j * (triangles_per_edge + 1) + i  # bottom left
            p10 = j * (triangles_per_edge + 1) + i + 1  # bottom right
            p01 = (j + 1) * (triangles_per_edge + 1) + i  # top left
            p11 = (j + 1) * (triangles_per_edge + 1) + i + 1  # top right
            pzz = index + (j * triangles_per_edge + i)  # vertex at centre of cell

            if mirror_y or flip_faces:
                faces.append([p00, pzz, p10])
                faces.append([p10, pzz, p11])
                faces.append([p11, pzz, p01])
                faces.append([p01, pzz, p00])
            else:
                faces.append([p00, p10, pzz])
                faces.append([p10, p11, pzz])
                faces.append([p11, p01, pzz])
                faces.append([p01, p00, pzz])

    faces = np.array(faces)

    # create the mesh object
    stl_mesh = mesh.Mesh(np.zeros(faces.shape[0], dtype=mesh.Mesh.dtype))
    for i, f in enumerate(faces):
        for j in range(3):
            stl_mesh.vectors[i][j] = vertices[f[j], :]

    return stl_mesh


def assess_inertial_properties(components: dict, component_densities: dict):
    """

    Parameters
    ----------
    components : dict
        A dictionary containing the mesh components to be analysed. Each key
        of the dict must contain another dict object, with keys "type" and
        "mesh". The "type" key is used to index the component density dict.
    component_densities : dict
        A dictionary containing the effective densities for each component.
        Note that the keys of the dict must match the "type" keys provided in
        the components dict.

    Returns
    -------
    total_volume : float
        The total volume.
    total_mass : float
        The toal mass.
    composite_cog : np.array
        The composite center of gravity.
    composite_inertia : np.array
        The composite mass moment of inertia.

    Examples
    --------
    >>> components = {'body': {'type': 'body', 'mesh': body},
                      'wings': {'type': 'wing', 'mesh': wings},
                      'inlet': {'type': 'inlet', 'mesh': inlet},
                      'fin1': {'type': 'fin', 'mesh': fin1},
                      'fin2': {'type': 'fin', 'mesh': fin2}}

    >>> component_densities = {'wing': 5590, 'body': 1680, 'inlet': 1680, 'fin': 5590}

    >>> volume, mass, cog, inertia = utils.assess_inertial_properties(components,
                                                             component_densities)
    """
    volumes = {}
    masses = {}
    cgs = {}
    inertias = {}
    total_mass = 0
    total_volume = 0
    for component, data in components.items():
        inertia_handle = getattr(data["mesh"], "get_mass_properties_with_density")

        volume, vmass, cog, inertia = inertia_handle(component_densities[data["type"]])

        volumes[component] = volume
        masses[component] = vmass
        cgs[component] = cog
        inertias[component] = inertia
        total_mass += vmass
        total_volume += volume

    # Composite centre of mass
    composite_cog = 0
    for component in components:
        m = masses[component]
        composite_cog += m * cgs[component]

    composite_cog *= 1 / total_mass

    # Parallel axis theorem
    shifted_inertias = {}
    composite_inertia = 0
    for component in components:
        m = masses[component]
        r = cgs[component] - composite_cog
        I_adj = inertias[component] + m * r**2

        shifted_inertias[component] = I_adj
        composite_inertia += I_adj

    return total_volume, total_mass, composite_cog, composite_inertia


class SensitivityStudy:
    """
    Computes the geometric sensitivities using finite differencing.
    """

    def __init__(self, vehicle_constructor=None, verbosity: int = 1):
        """Vehicle geometry sensitivity constructor.

        Parameters
        ----------
        vehicle_constructor : TYPE
            The Vehicle instance constructor.

        Returns
        -------
        VehicleSensitivity object.

        """
        self.vehicle_constructor = vehicle_constructor
        self.verbosity = verbosity

        # Parameter sensitivities
        self.sensitivities = None

    def __repr__(self):
        return "HyperVehicle sensitivity study"

    def dGdP(
        self,
        parameter_dict: dict,
        perturbation: float = 20,
        vehicle_creator_method: str = "create_instance",
        write_nominal_stl: bool = True,
    ):
        """Computes the sensitivity of the geometry with respect to the
        parameters.

        Parameters
        ----------
        parameter_dict : dict
            A dictionary of the design parameters to perturb, and their
            nominal values.
        perturbation : float, optional
            The design parameter perturbation amount, specified as percentage.
            The default is 20.
        vehicle_creator_method : str, optional
            The name of the method which returns a hypervehicle.Vehicle
            instance, ready for generation. The default is 'create_instance'.
        write_nominal_stl : bool, optional
            A boolean flag to write the nominal geometry STL(s) to file. The
            default is True.

        Returns
        -------
        sensitivities : TYPE
            A dictionary containing the sensitivity information for all
            components of the geometry, relative to the nominal geometry.

        """
        # Create Vehicle instance with nominal parameters
        if self.verbosity > 0:
            print("Generating nominal geometry...")
        constructor_instance = self.vehicle_constructor(**parameter_dict)
        nominal_instance = getattr(constructor_instance, vehicle_creator_method)()
        nominal_instance.write_stl = write_nominal_stl
        nominal_instance.verbosity = 0

        # Generate stl meshes
        nominal_instance.generate()
        nominal_meshes = nominal_instance.meshes
        if self.verbosity > 0:
            print("  Done.")

        sensitivities = {}

        # Generate meshes for each parameter
        if self.verbosity > 0:
            print("Generating perturbed geometries...")
        for parameter, value in parameter_dict.items():
            # Create copy
            adjusted_parameters = parameter_dict.copy()

            # Adjust current parameter for sensitivity analysis
            adjusted_parameters[parameter] *= 1 + perturbation / 100
            dP = adjusted_parameters[parameter] - value

            # Create Vehicle instance with perturbed parameter
            constructor_instance = self.vehicle_constructor(**adjusted_parameters)
            parameter_instance = getattr(constructor_instance, vehicle_creator_method)()
            parameter_instance.write_stl = False
            parameter_instance.verbosity = 0

            # Generate stl meshes
            parameter_instance.generate()
            parameter_meshes = parameter_instance.meshes

            # Generate sensitivities
            for component, meshes in nominal_meshes.items():
                sensitivities[component] = []
                for ix, nominal_mesh in enumerate(meshes):
                    parameter_mesh = parameter_meshes[component][ix]

                    component_mesh_name = f"{component}_{ix}"
                    sensitivity_df = self.compare_meshes(
                        nominal_mesh,
                        parameter_mesh,
                        dP,
                        component_mesh_name,
                        parameter,
                        True,
                    )

                    sensitivities[component].append(sensitivity_df)
        if self.verbosity > 0:
            print("  Done.")

        # Return output
        self.sensitivities = sensitivities

        # TODO - option to combine all sensitivities (new method)

        return sensitivities

    @staticmethod
    def compare_meshes(
        mesh1, mesh2, dP, component: str, parameter_name: str, save_csv: bool = False
    ) -> pd.DataFrame:
        """Compares two meshes with each other and applies finite differencing
        to quantify their differences.

        Parameters
        ----------
        mesh1 : None
            The reference mesh.
        mesh1 : None
            The perturbed mesh.
        dP : None
        component : str
            The component name.
        parameter_name : str
            The name of the parameter.
        save_csv : bool, optional
            Write the differences to a CSV file. The default is True.

        Returns
        --------
        df : pd.DataFrame
            A DataFrame of the finite difference results.
        """
        # Take the vector difference
        diff = mesh2.vectors - mesh1.vectors

        # Resize difference array to flatten
        shape = diff.shape
        flat_diff = diff.reshape((shape[0] * shape[2], shape[1]))

        # Also flatten the reference mesh vectors
        vectors = mesh1.vectors.reshape((shape[0] * shape[2], shape[1]))

        # Concatenate all data column-wise
        all_data = np.zeros((shape[0] * shape[2], shape[1] * 2))
        all_data[:, 0:3] = vectors  # Reference locations
        all_data[:, 3:6] = flat_diff  # Location deltas

        # Create DataFrame
        df = pd.DataFrame(data=all_data, columns=["x", "y", "z", "dx", "dy", "dz"])
        df["magnitude"] = np.sqrt(np.square(df[["dx", "dy", "dz"]]).sum(axis=1))

        # Sensitivity calculations
        sensitivities = df[["dx", "dy", "dz"]] / dP
        sensitivities.rename(
            columns={"dx": "dxdP", "dy": "dydP", "dz": "dzdP"}, inplace=True
        )

        # Merge dataframes
        df = df.merge(sensitivities, left_index=True, right_index=True)

        # Delete duplicate vertices
        df = df[~df.duplicated()]

        if save_csv:
            # Save to csv format for visualisation
            df.to_csv(f"{component}_{parameter_name}_sensitivity.csv", index=False)

        return df


def append_sensitivities_to_tri(
    dp_files: list,
    components_filepath: str = "Components.i.tri",
    sensitivity_name: str = None,
):
    """Appends shape sensitivity data to .i.tri file.

    Parameters
    ----------
    dp_files : list[str]
        A list of the file names of the sensitivity data.
    components_filepath : str, optional
        The filepath to the .tri file to be appended to. The default is
        'Components.i.tri'.
    sensitivity_name : str, optional
        The name of the design feature which the sensitivity is to. If None,
        this will be detrived from the inputted dp_files. The default is None.

    Examples
    ---------
    >>> dp_files = ['wing_0_body_width_sensitivity.csv',
                    'wing_1_body_width_sensitivity.csv']

    """
    # Parse .tri file
    tree = ET.parse(components_filepath)
    root = tree.getroot()
    grid = root[0]
    piece = grid[0]
    points = piece[0]

    points_data = points[0].text

    points_data_list = [el.split() for el in points_data.splitlines()]
    points_data_list = [[float(j) for j in i] for i in points_data_list]

    points_df = pd.DataFrame(points_data_list, columns=["x", "y", "z"]).dropna()

    # Load and concatenate sensitivity data
    dp_df = pd.DataFrame()
    for file in dp_files:
        df = pd.read_csv(file)
        dp_df = pd.concat([dp_df, df])

    # Match points_df to sensitivity df
    data_str = "\n "
    for i in range(len(points_df)):
        tolerance = 1e-5
        match_x = (points_df["x"].iloc[i] - dp_df["x"]).abs() < tolerance
        match_y = (points_df["y"].iloc[i] - dp_df["y"]).abs() < tolerance
        match_z = (points_df["z"].iloc[i] - dp_df["z"]).abs() < tolerance

        match = match_x & match_y & match_z
        try:
            # What if there are multiple matches? (due to intersect perturbations)
            matched_data = dp_df[match].iloc[0][["dxdP", "dydP", "dzdP"]].values

            # Round off infinitesimally small values
            matched_data[abs(matched_data) < 1e-8] = 0

            line = ""
            for i in range(3):
                line += f"\t{matched_data[i]:.14e}"
            line += "\n "
            # data_str += f'{matched_data[0]} {matched_data[1]} {matched_data[2]}\n '

        except:
            # No match found, append zeros to maintain order
            line = f"\t{0:.14e}\t{0:.14e}\t{0:.14e}\n "
            # data_str += '0 0 0\n '
        data_str += line

    # Write the matched sensitivity df to i.tri file as new xml element
    # NumberOfComponents is how many sensitivity components there are (3 for x,y,z)
    if sensitivity_name is None:
        # Attempt to construct sensitivity name
        filename = dp_files[0]
        sensitivity_name = "".join("".join(filename.split("_")[2:]).split(".")[:-1])

    attribs = {
        "Name": f"{sensitivity_name}",
        "NumberOfComponents": "3",
        "type": "Float64",
        "format": "ascii",
        "TRIXtype": "SHAPE_LINEARIZATION",
    }
    PointData = ET.SubElement(piece, "PointData")
    PointDataArray = ET.SubElement(PointData, "DataArray", attribs)
    PointDataArray.text = data_str

    # Save to file
    tree.write(components_filepath)


def csv_to_delaunay(filepath: str):
    """Converts a csv file of points to a Delaunay3D surface.

    Parameters
    ------------
    filepath : str
            The filepath to the CSV file.
    """
    # TODO - rename
    from paraview.simple import CSVReader, TableToPoints, Delaunay3D, SaveData

    root_dir = os.path.dirname(filepath)
    prefix = filepath.split(os.sep)[-1].split(".csv")[0]
    savefilename = os.path.join(root_dir, f"{prefix}.vtu")

    # create a new 'CSV Reader'
    fin_0_L_b_sensitivitycsv = CSVReader(FileName=[filepath])

    # create a new 'Table To Points'
    tableToPoints1 = TableToPoints(Input=fin_0_L_b_sensitivitycsv)

    # Properties modified on tableToPoints1
    tableToPoints1.XColumn = "x"
    tableToPoints1.YColumn = "y"
    tableToPoints1.ZColumn = "z"

    # create a new 'Delaunay 3D'
    delaunay3D1 = Delaunay3D(Input=tableToPoints1)

    # save data
    SaveData(savefilename, proxy=delaunay3D1)


def convert_all_csv_to_delaunay(directory: str = ""):
    # TODO - rename
    # TODO - docstrings
    # TODO - specify outdir
    files = glob.glob(os.path.join(directory, "*.csv"))

    if len(files) == 0:
        print(f"No CSV files in directory {directory}.")
        sys.exit()

    for file in files:
        csv_to_delaunay(file)
