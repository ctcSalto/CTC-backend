from external_services.moodle_api.controllers.moodle_base_controller import BaseMoodleController
from external_services.moodle_api.moodle_config import EnrolmentRole
from external_services.moodle_api.models.enrolment import MoodleEnrolmentCreate, MoodleEnrolmentRead, MoodleBulkEnrolmentCreate, MoodleBulkEnrolmentRead, MoodleUnenrolmentCreate, MoodleUnenrolmentRead, EnrolledUser, CourseEnrolledUsers
from typing import List, Dict

class EnrolmentController(BaseMoodleController):
    
    def enrol_user(self, enrolment_data: MoodleEnrolmentCreate) -> MoodleEnrolmentRead:
        """Inscribir usuario en curso con rol específico"""
        try:
            # Validar que el roleid sea válido
            valid_roles = [role.value for role in EnrolmentRole]
            if enrolment_data.roleid not in valid_roles:
                raise ValueError(f"Rol inválido. Roles válidos: {valid_roles}")
            
            payload = {
                "enrolments[0][roleid]": str(enrolment_data.roleid),
                "enrolments[0][userid]": str(enrolment_data.userid),
                "enrolments[0][courseid]": str(enrolment_data.courseid)
            }
            
            # Hacer la petición a Moodle
            moodle_response = self._make_request("enrol_manual_enrol_users", payload)
            
            # Procesar respuesta de Moodle y crear el objeto de respuesta
            return MoodleEnrolmentRead(
                success=True,
                courseid=enrolment_data.courseid,
                userid=enrolment_data.userid,
                roleid=enrolment_data.roleid,
                message="Usuario inscrito exitosamente"
            )
            
        except Exception as e:
            return MoodleEnrolmentRead(
                success=False,
                courseid=enrolment_data.courseid,
                userid=enrolment_data.userid,
                roleid=enrolment_data.roleid,
                message=f"Error al inscribir usuario: {str(e)}"
            )

    def enrol_users_bulk(self, enrolments_data: MoodleBulkEnrolmentCreate) -> MoodleBulkEnrolmentRead:
        """Inscribir múltiples usuarios en cursos con roles específicos"""
        results = []
        successful = 0
        failed = 0
        
        try:
            # Validar todos los roles antes de procesar
            valid_roles = [role.value for role in EnrolmentRole]
            for enrolment in enrolments_data.enrolments:
                if enrolment.roleid not in valid_roles:
                    raise ValueError(f"Rol inválido: {enrolment.roleid}. Roles válidos: {valid_roles}")
            
            # Preparar payload para Moodle
            payload = {}
            for i, enrolment in enumerate(enrolments_data.enrolments):
                payload[f"enrolments[{i}][roleid]"] = str(enrolment.roleid)
                payload[f"enrolments[{i}][userid]"] = str(enrolment.userid)
                payload[f"enrolments[{i}][courseid]"] = str(enrolment.courseid)
            
            # Hacer la petición a Moodle
            moodle_response = self._make_request("enrol_manual_enrol_users", payload)
            
            # Procesar resultados individuales
            for enrolment in enrolments_data.enrolments:
                result = MoodleEnrolmentRead(
                    success=True,
                    courseid=enrolment.courseid,
                    userid=enrolment.userid,
                    roleid=enrolment.roleid,
                    message="Usuario inscrito exitosamente"
                )
                results.append(result)
                successful += 1
                
        except Exception as e:
            # Si falla la operación masiva, marcar todos como fallidos
            for enrolment in enrolments_data.enrolments:
                result = MoodleEnrolmentRead(
                    success=False,
                    courseid=enrolment.courseid,
                    userid=enrolment.userid,
                    roleid=enrolment.roleid,
                    message=f"Error al inscribir usuario: {str(e)}"
                )
                results.append(result)
                failed += 1
            
            return MoodleBulkEnrolmentRead(
                total_enrolments=len(enrolments_data.enrolments),
                successful_enrolments=successful,
                failed_enrolments=failed,
                results=results,
                message=f"Procesadas {len(enrolments_data.enrolments)} inscripciones. Exitosas: {successful}, Fallidas: {failed}"
            )

    def unenrol_user(self, unenrolment_data: MoodleUnenrolmentCreate) -> MoodleUnenrolmentRead:
        """Desinscribir usuario de curso"""
        try:
            payload = {
                "enrolments[0][userid]": str(unenrolment_data.userid),
                "enrolments[0][courseid]": str(unenrolment_data.courseid)
            }
            
            # Hacer la petición a Moodle
            moodle_response = self._make_request("enrol_manual_unenrol_users", payload)
            
            return MoodleUnenrolmentRead(
                success=True,
                courseid=unenrolment_data.courseid,
                userid=unenrolment_data.userid,
                message="Usuario desinscrito exitosamente"
            )
            
        except Exception as e:
            return MoodleUnenrolmentRead(
                success=False,
                courseid=unenrolment_data.courseid,
                userid=unenrolment_data.userid,
                message=f"Error al desinscribir usuario: {str(e)}"
            )
    
    def get_enrolled_users(self, course_id: int) -> CourseEnrolledUsers:
        """Obtener usuarios inscritos en un curso"""
        try:
            payload = {
                "courseid": str(course_id)
            }
            
            # Hacer la petición a Moodle
            moodle_response = self._make_request("core_enrol_get_enrolled_users", payload)
            
            # Procesar la respuesta
            users = []
            if isinstance(moodle_response, list):
                for user_data in moodle_response:
                    user = EnrolledUser(
                        id=user_data.get('id', 0),
                        username=user_data.get('username', ''),
                        firstname=user_data.get('firstname', ''),
                        lastname=user_data.get('lastname', ''),
                        email=user_data.get('email', ''),
                        roles=user_data.get('roles', [])
                    )
                    users.append(user)
            
            return CourseEnrolledUsers(
                courseid=course_id,
                total_users=len(users),
                users=users
            )
            
        except Exception as e:
            # Retornar estructura vacía en caso de error
            return CourseEnrolledUsers(
                courseid=course_id,
                total_users=0,
                users=[]
            )